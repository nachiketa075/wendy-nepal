"""Business rules for table-booking requests.

Requests are never auto-confirmed and no table capacity is tracked: checking
availability is left to staff, who confirm or decline each request.
"""

import datetime as dt
import hashlib
import json
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import activity
from .config import get_settings
from .errors import ApiError
from .models import Account, Booking, BookingDateOverride, BookingSettings, BookingStatusHistory, BookingWindow
from .permissions import ALLOWED_TRANSITIONS, TRANSITION_PERMISSION
from .schemas import BookingCreate, CancellationOut, CustomerBookingOut, HistoryEntry, PersonRef, StaffBookingOut

logger = logging.getLogger("wendy.bookings")

RECEIVED_MESSAGE = (
    "Your request has been received. Your table is not confirmed yet. "
    "The team will contact you after checking availability."
)

# No 0/O or 1/I so references are easy to read back over the phone.
_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CANCELLABLE_BY_REQUEST = ("pending", "confirmed")


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


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(422, "validation_error", "Please check the highlighted details.", {field: message})


def windows_for(db: Session, date: dt.date) -> list[tuple[dt.time, dt.time]] | None:
    """Booking windows for a date. None means the date is closed by an override."""
    override = db.scalar(select(BookingDateOverride).where(BookingDateOverride.date == date))
    if override is not None:
        return None if override.is_closed else [(override.start_time, override.end_time)]
    rows = db.scalars(select(BookingWindow).where(BookingWindow.weekday == date.weekday())).all()
    return [(w.start_time, w.end_time) for w in rows]


def validate_request(db: Session, settings: BookingSettings, data: BookingCreate) -> dt.datetime:
    """Apply business rules; return the requested moment in the business timezone."""
    if not accepting_requests(settings):
        raise ApiError(
            409,
            "booking_unavailable",
            "Online table requests are not open at the moment. Please call us instead.",
        )

    if not settings.min_party_size <= data.party_size <= settings.max_party_size:
        raise _invalid(
            "party_size",
            f"Online requests are for {settings.min_party_size} to {settings.max_party_size} guests. "
            "For other group sizes please call us.",
        )

    now = now_local()
    requested_at = dt.datetime.combine(data.requested_date, data.requested_time, tzinfo=now.tzinfo)
    if requested_at <= now:
        raise _invalid("requested_date", "That date and time has already passed (Pokhara time).")
    if requested_at < now + dt.timedelta(minutes=settings.min_lead_minutes):
        raise _invalid("requested_time", "That is too soon to request online. Please call us for a table right away.")
    if data.requested_date > now.date() + dt.timedelta(days=settings.max_advance_days):
        raise _invalid("requested_date", f"Requests can be made up to {settings.max_advance_days} days ahead.")

    windows = windows_for(db, data.requested_date)
    if windows is None:
        raise _invalid("requested_date", "We are not taking table requests on that date.")
    if not windows:
        raise _invalid("requested_date", "Table requests are not taken for that day.")
    minutes = data.requested_time.hour * 60 + data.requested_time.minute
    for start_time, end_time in windows:
        start = start_time.hour * 60 + start_time.minute
        end = end_time.hour * 60 + end_time.minute
        if start <= minutes <= end and (minutes - start) % settings.slot_interval_minutes == 0:
            return requested_at
    raise _invalid("requested_time", "Please choose one of the listed times for that day.")


def _request_hash(data: BookingCreate, customer_id: int | None) -> str:
    payload = data.model_dump(mode="json", exclude={"idempotency_key"})
    payload["customer_id"] = customer_id
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _find_duplicate(db: Session, data: BookingCreate, customer_id: int | None, request_hash: str) -> Booking | None:
    if data.idempotency_key:
        by_key = db.scalar(select(Booking).where(Booking.idempotency_key == data.idempotency_key))
        if by_key is not None:
            if by_key.request_hash != request_hash:
                raise ApiError(
                    409,
                    "idempotency_conflict",
                    "This request was already sent with different details. Please refresh the page and try again.",
                )
            return by_key
    # The same person asking for the same slot again while still pending.
    return db.scalar(
        select(Booking).where(
            Booking.phone == data.phone,
            Booking.requested_date == data.requested_date,
            Booking.requested_time == data.requested_time,
            Booking.party_size == data.party_size,
            Booking.status == "pending",
            Booking.customer_id.is_not_distinct_from(customer_id),
        )
    )


def create_booking(db: Session, data: BookingCreate, customer: Account | None = None) -> tuple[Booking, bool]:
    """Persist a pending request. Returns (booking, created).

    The customer link comes only from the authenticated session. Status,
    reference, assignment and notes are always set here, never by the client.
    """
    customer_id = customer.id if customer else None
    request_hash = _request_hash(data, customer_id)
    existing = _find_duplicate(db, data, customer_id, request_hash)
    if existing is not None:
        return existing, False

    settings = get_booking_settings(db)
    requested_at = validate_request(db, settings, data)

    for _ in range(5):
        booking = Booking(
            reference=_new_reference(),
            idempotency_key=data.idempotency_key,
            request_hash=request_hash,
            customer_id=customer_id,
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
        booking.history.append(
            BookingStatusHistory(
                from_status=None,
                to_status="pending",
                actor_id=customer_id,
                actor_role="customer" if customer else "guest",
            )
        )
        db.add(booking)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Either a concurrent retry with the same key won the race, or the
            # random reference collided; in the latter case try a new one.
            existing = _find_duplicate(db, data, customer_id, request_hash)
            if existing is not None:
                return existing, False
            continue
        # Contact details are deliberately kept out of the logs.
        logger.info("booking request stored reference=%s", booking.reference)
        return booking, True

    raise ApiError(500, "save_failed", "We could not save your request. Please try again or call us.")


# ---------- staff actions ----------


def can_view(actor: Account, booking: Booking) -> bool:
    if actor.can("bookings.view_all"):
        return True
    return actor.can("bookings.view_assigned") and booking.assigned_employee_id == actor.id


def load_for_update(db: Session, booking_id: int, actor: Account) -> Booking:
    """Lock the booking row for this transaction and check the actor may see it.

    A booking outside the actor's scope is reported as missing, not forbidden.
    """
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None or not can_view(actor, booking):
        db.rollback()
        raise ApiError(404, "not_found", "That booking request does not exist.")
    return booking


def _check_version(db: Session, booking: Booking, expected: int) -> None:
    if booking.version != expected:
        db.rollback()
        raise ApiError(
            409,
            "stale_update",
            "Someone else changed this booking a moment ago. It has been reloaded; please check and try again.",
        )


def _time_rule(booking: Booking, new_status: str) -> str | None:
    """Why this transition is not possible at this moment, or None if it is."""
    now = now_local()
    if new_status == "confirmed" and booking.requested_at <= now:
        return "The requested time has already passed, so this request can no longer be confirmed."
    if new_status == "checked_in" and booking.requested_date != now.date():
        return "Guests can only be checked in on the day of their booking."
    if new_status == "no_show" and booking.requested_at > now:
        return "A booking can only be marked as a no-show after its time has passed."
    return None


def allowed_statuses(actor: Account, booking: Booking) -> list[str]:
    return [
        status
        for status in ("confirmed", "declined", "checked_in", "completed", "no_show", "cancelled")
        if status in ALLOWED_TRANSITIONS[booking.status]
        and actor.can(TRANSITION_PERMISSION[status])
        and _time_rule(booking, status) is None
    ]


def _touch(booking: Booking) -> None:
    booking.version += 1


def change_status(db: Session, booking: Booking, new_status: str, actor: Account, expected_version: int,
                  reason: str | None = None) -> Booking:
    """Apply a status change to a row already locked by load_for_update."""
    _check_version(db, booking, expected_version)
    if new_status not in ALLOWED_TRANSITIONS[booking.status]:
        db.rollback()
        raise ApiError(409, "invalid_transition", f"A {booking.status.replace('_', ' ')} booking cannot be changed to {new_status.replace('_', ' ')}.")
    if not actor.can(TRANSITION_PERMISSION[new_status]):
        db.rollback()
        raise ApiError(403, "forbidden", "You don't have permission to do that.")
    problem = _time_rule(booking, new_status)
    if problem:
        db.rollback()
        raise ApiError(409, "not_allowed_now", problem)

    now = dt.datetime.now(dt.UTC)
    previous = booking.status
    booking.status = new_status
    booking.status_changed_at = now
    if new_status == "cancelled" and booking.cancellation_status == "pending":
        booking.cancellation_status = "approved"
        booking.cancellation_resolved_at = now
        booking.cancellation_resolved_by_id = actor.id
    _touch(booking)
    booking.history.append(
        BookingStatusHistory(from_status=previous, to_status=new_status, actor_id=actor.id, actor_role=actor.role, reason=reason)
    )
    activity.record(db, actor, "booking.status", "booking", booking.reference, from_status=previous, to_status=new_status, reason=reason)
    db.commit()
    logger.info("booking status changed reference=%s status=%s", booking.reference, new_status)
    return booking


def update_notes(db: Session, booking: Booking, notes: str | None, actor: Account, expected_version: int) -> Booking:
    _check_version(db, booking, expected_version)
    booking.internal_notes = notes
    _touch(booking)
    activity.record(db, actor, "booking.notes", "booking", booking.reference)
    db.commit()
    return booking


def assign(db: Session, booking: Booking, employee: Account | None, actor: Account, expected_version: int) -> Booking:
    _check_version(db, booking, expected_version)
    booking.assigned_employee_id = employee.id if employee else None
    _touch(booking)
    activity.record(db, actor, "booking.assign", "booking", booking.reference, employee=employee.full_name if employee else None)
    db.commit()
    db.refresh(booking)
    return booking


def resolve_cancellation(db: Session, booking: Booking, approve: bool, actor: Account, expected_version: int,
                         response: str | None) -> Booking:
    _check_version(db, booking, expected_version)
    if booking.cancellation_status != "pending":
        db.rollback()
        raise ApiError(409, "no_pending_request", "There is no open cancellation request on this booking.")
    now = dt.datetime.now(dt.UTC)
    if approve:
        if "cancelled" not in ALLOWED_TRANSITIONS[booking.status]:
            db.rollback()
            raise ApiError(409, "invalid_transition", f"A {booking.status.replace('_', ' ')} booking cannot be cancelled.")
        previous = booking.status
        booking.status = "cancelled"
        booking.status_changed_at = now
        booking.history.append(
            BookingStatusHistory(from_status=previous, to_status="cancelled", actor_id=actor.id, actor_role=actor.role,
                                 reason="Cancellation requested by the customer")
        )
    booking.cancellation_status = "approved" if approve else "declined"
    booking.cancellation_resolved_at = now
    booking.cancellation_resolved_by_id = actor.id
    booking.cancellation_response = response
    _touch(booking)
    activity.record(db, actor, "booking.cancellation_resolved", "booking", booking.reference, decision=booking.cancellation_status)
    db.commit()
    return booking


def request_cancellation(db: Session, reference: str, customer: Account, reason: str | None) -> Booking:
    """A customer asks to cancel their own booking. Staff decide; the status is unchanged here."""
    booking = db.scalar(
        select(Booking).where(Booking.reference == reference, Booking.customer_id == customer.id).with_for_update()
    )
    if booking is None:
        db.rollback()
        raise ApiError(404, "not_found", "We couldn't find that booking.")
    if booking.status not in CANCELLABLE_BY_REQUEST:
        db.rollback()
        raise ApiError(409, "not_cancellable", f"A {booking.status.replace('_', ' ')} booking cannot be cancelled.")
    if booking.cancellation_status == "pending":
        db.rollback()
        raise ApiError(409, "already_requested", "You have already asked to cancel this booking. The team will reply soon.")
    booking.cancellation_status = "pending"
    booking.cancellation_reason = reason
    booking.cancellation_requested_at = dt.datetime.now(dt.UTC)
    booking.cancellation_resolved_at = None
    booking.cancellation_resolved_by_id = None
    booking.cancellation_response = None
    _touch(booking)
    activity.record(db, customer, "booking.cancellation_requested", "booking", booking.reference)
    db.commit()
    return booking


# ---------- serialisation ----------


def _cancellation(booking: Booking) -> CancellationOut | None:
    if booking.cancellation_status is None:
        return None
    return CancellationOut(
        status=booking.cancellation_status,
        reason=booking.cancellation_reason,
        requested_at=booking.cancellation_requested_at,
        resolved_at=booking.cancellation_resolved_at,
        response=booking.cancellation_response,
    )


def customer_view(booking: Booking) -> CustomerBookingOut:
    return CustomerBookingOut(
        reference=booking.reference,
        status=booking.status,
        full_name=booking.full_name,
        phone=booking.phone,
        email=booking.email,
        requested_date=booking.requested_date,
        requested_time=booking.requested_time,
        party_size=booking.party_size,
        special_requests=booking.special_requests,
        created_at=booking.created_at,
        status_changed_at=booking.status_changed_at,
        cancellation=_cancellation(booking),
        can_request_cancellation=booking.status in CANCELLABLE_BY_REQUEST and booking.cancellation_status != "pending",
    )


def staff_view(booking: Booking, actor: Account, with_history: bool = False) -> StaffBookingOut:
    """Build the staff response. Contact fields are left out of the payload
    itself when the viewer lacks bookings.view_contact."""
    contact = actor.can("bookings.view_contact")
    history = None
    if with_history:
        history = [
            HistoryEntry(
                from_status=h.from_status,
                to_status=h.to_status,
                actor=h.actor.full_name if h.actor and h.actor_role in ("owner", "employee") else h.actor_role.capitalize(),
                actor_role=h.actor_role,
                reason=h.reason,
                created_at=h.created_at,
            )
            for h in booking.history
        ]
    assignee = booking.assigned_employee
    return StaffBookingOut(
        id=booking.id,
        reference=booking.reference,
        full_name=booking.full_name,
        contact_visible=contact,
        phone=booking.phone if contact else None,
        email=booking.email if contact else None,
        requested_date=booking.requested_date,
        requested_time=booking.requested_time,
        party_size=booking.party_size,
        special_requests=booking.special_requests,
        status=booking.status,
        internal_notes=booking.internal_notes,
        version=booking.version,
        has_account=booking.customer_id is not None,
        created_at=booking.created_at,
        status_changed_at=booking.status_changed_at,
        assigned_employee=PersonRef(id=assignee.id, full_name=assignee.full_name) if assignee else None,
        cancellation=_cancellation(booking),
        allowed_statuses=allowed_statuses(actor, booking),
        can_edit_notes=actor.can("bookings.edit_notes"),
        can_resolve_cancellation=booking.cancellation_status == "pending" and actor.can("bookings.cancel"),
        history=history,
    )
