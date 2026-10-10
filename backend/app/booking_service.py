"""Business rules for table-booking requests.

Requests are never auto-confirmed and no table capacity is tracked: checking
availability is left to the owner, who confirms or declines each request.
"""

import datetime as dt
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .errors import ApiError
from .models import Booking, BookingSettings, BookingWindow
from .schemas import BookingCreate

logger = logging.getLogger("wendy.bookings")

RECEIVED_MESSAGE = (
    "Your request has been received. Your table is not confirmed yet. "
    "The team will contact you after checking availability."
)

# No 0/O or 1/I so references are easy to read back over the phone.
_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

ALLOWED_TRANSITIONS = {
    "pending": {"confirmed", "declined", "cancelled"},
    "confirmed": {"cancelled"},
    "declined": set(),
    "cancelled": set(),
}


def now_local() -> dt.datetime:
    return dt.datetime.now(get_settings().tz)


def get_booking_settings(db: Session) -> BookingSettings:
    settings = db.get(BookingSettings, 1)
    if settings is None:
        raise ApiError(503, "not_configured", "Booking settings are missing. Run the database migrations.")
    return settings


def accepting_requests(settings: BookingSettings) -> bool:
    """Provisional demo settings must be confirmed by the owner before real use."""
    if not settings.booking_enabled:
        return False
    if get_settings().environment == "production" and not settings.owner_confirmed:
        return False
    return True


def _new_reference() -> str:
    return "WJ-" + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(6))


def validate_request(db: Session, settings: BookingSettings, data: BookingCreate) -> dt.datetime:
    """Apply business rules; return the requested moment in the business timezone."""
    if not accepting_requests(settings):
        raise ApiError(
            409,
            "booking_unavailable",
            "Online table requests are not open at the moment. Please call us instead.",
        )

    if not settings.min_party_size <= data.party_size <= settings.max_party_size:
        raise ApiError(
            422,
            "validation_error",
            "Please check the highlighted details.",
            {
                "party_size": f"Online requests are for {settings.min_party_size} to "
                f"{settings.max_party_size} guests. For other group sizes please call us."
            },
        )

    now = now_local()
    requested_at = dt.datetime.combine(data.requested_date, data.requested_time, tzinfo=now.tzinfo)
    if requested_at <= now:
        raise ApiError(
            422,
            "validation_error",
            "Please check the highlighted details.",
            {"requested_date": "That date and time has already passed (Pokhara time)."},
        )
    if requested_at < now + dt.timedelta(minutes=settings.min_lead_minutes):
        raise ApiError(
            422,
            "validation_error",
            "Please check the highlighted details.",
            {"requested_time": "That is too soon to request online. Please call us for a table right away."},
        )
    if data.requested_date > now.date() + dt.timedelta(days=settings.max_advance_days):
        raise ApiError(
            422,
            "validation_error",
            "Please check the highlighted details.",
            {"requested_date": f"Requests can be made up to {settings.max_advance_days} days ahead."},
        )

    windows = db.scalars(
        select(BookingWindow).where(BookingWindow.weekday == data.requested_date.weekday())
    ).all()
    if not windows:
        raise ApiError(
            422,
            "validation_error",
            "Please check the highlighted details.",
            {"requested_date": "Table requests are not taken for that day."},
        )
    minutes = data.requested_time.hour * 60 + data.requested_time.minute
    for window in windows:
        start = window.start_time.hour * 60 + window.start_time.minute
        end = window.end_time.hour * 60 + window.end_time.minute
        if start <= minutes <= end and (minutes - start) % settings.slot_interval_minutes == 0:
            return requested_at
    raise ApiError(
        422,
        "validation_error",
        "Please check the highlighted details.",
        {"requested_time": "Please choose one of the listed times for that day."},
    )


def _find_duplicate(db: Session, data: BookingCreate) -> Booking | None:
    if data.idempotency_key:
        by_key = db.scalar(select(Booking).where(Booking.idempotency_key == data.idempotency_key))
        if by_key is not None:
            return by_key
    # The same guest asking for the same slot again while still pending.
    return db.scalar(
        select(Booking).where(
            Booking.phone == data.phone,
            Booking.requested_date == data.requested_date,
            Booking.requested_time == data.requested_time,
            Booking.party_size == data.party_size,
            Booking.status == "pending",
        )
    )


def create_booking(db: Session, data: BookingCreate) -> tuple[Booking, bool]:
    """Persist a pending request. Returns (booking, created)."""
    existing = _find_duplicate(db, data)
    if existing is not None:
        return existing, False

    settings = get_booking_settings(db)
    requested_at = validate_request(db, settings, data)

    for _ in range(5):
        booking = Booking(
            reference=_new_reference(),
            idempotency_key=data.idempotency_key,
            full_name=data.full_name,
            phone=data.phone,
            email=str(data.email) if data.email else None,
            requested_date=data.requested_date,
            requested_time=data.requested_time,
            requested_at=requested_at,
            party_size=data.party_size,
            special_requests=data.special_requests,
            status="pending",
        )
        db.add(booking)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Either a concurrent retry with the same key won the race, or the
            # random reference collided; in the latter case try a new one.
            existing = _find_duplicate(db, data)
            if existing is not None:
                return existing, False
            continue
        # Contact details are deliberately kept out of the logs.
        logger.info("booking request stored reference=%s", booking.reference)
        return booking, True

    raise ApiError(500, "save_failed", "We could not save your request. Please try again or call us.")


def change_status(db: Session, booking: Booking, new_status: str) -> Booking:
    if new_status not in ALLOWED_TRANSITIONS[booking.status]:
        raise ApiError(
            409,
            "invalid_transition",
            f"A {booking.status} request cannot be changed to {new_status}.",
        )
    booking.status = new_status
    booking.status_changed_at = dt.datetime.now(dt.UTC)
    db.commit()
    logger.info("booking status changed reference=%s status=%s", booking.reference, new_status)
    return booking
