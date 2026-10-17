import datetime as dt
import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from .. import booking_service
from ..config import get_settings
from ..database import get_db
from ..models import BookingDateOverride, BookingWindow, MenuCategory
from ..rate_limit import client_ip, limiter
from ..schemas import BookingCreate, BookingReceipt, PublicBookingConfig, PublicMenu

router = APIRouter(prefix="/api", tags=["public"])
logger = logging.getLogger("wendy.health")

# The newest migration in alembic/versions. Update when adding a migration.
EXPECTED_REVISION = "0004"


@router.get("/health")
def health() -> dict:
    """Liveness: the API process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness: the database answers and its schema is the one this code expects.
    Reports only ok / not ready, never connection details."""
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001 - any database failure means "not ready"
        logger.error("readiness check: database unavailable")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    if revision != EXPECTED_REVISION:
        logger.error("readiness check: database schema is not at the expected migration")
        return JSONResponse({"status": "migration_pending"}, status_code=503)
    return {"status": "ready"}


@router.get("/menu", response_model=PublicMenu)
def get_menu(db: Session = Depends(get_db)):
    """The one menu, from the database. Hidden items and empty sections are left out."""
    categories = db.scalars(
        select(MenuCategory).options(selectinload(MenuCategory.items)).order_by(MenuCategory.sort_order, MenuCategory.id)
    ).all()
    out = []
    for category in categories:
        items = [item for item in category.items if item.is_published]
        if items:
            out.append({"id": category.id, "slug": category.slug, "name": category.name, "tagline": category.tagline,
                        "sort_order": category.sort_order, "notes": category.notes or [], "items": items})
    return {"categories": out}


@router.get("/booking/config", response_model=PublicBookingConfig)
def booking_config(db: Session = Depends(get_db)):
    settings = booking_service.get_booking_settings(db)
    today = booking_service.now_local().date()
    windows = db.scalars(select(BookingWindow).order_by(BookingWindow.weekday, BookingWindow.start_time)).all()
    overrides = db.scalars(
        select(BookingDateOverride)
        .where(BookingDateOverride.date >= today,
               BookingDateOverride.date <= today + dt.timedelta(days=settings.max_advance_days))
        .order_by(BookingDateOverride.date)
    ).all()
    return PublicBookingConfig(
        accepting_requests=booking_service.accepting_requests(settings),
        timezone=get_settings().business_timezone,
        today=today,
        min_party_size=settings.min_party_size,
        max_party_size=settings.max_party_size,
        min_lead_minutes=settings.min_lead_minutes,
        max_advance_days=settings.max_advance_days,
        slot_interval_minutes=settings.slot_interval_minutes,
        windows=windows,
        overrides=overrides,
    )


@router.post("/bookings", response_model=BookingReceipt, status_code=201)
def create_booking(data: BookingCreate, request: Request, response: Response, db: Session = Depends(get_db)):
    """Guest request (no account). The response never includes guest details,
    and there is no endpoint to look a booking up by its reference."""
    ip = client_ip(request)
    limiter.hit(f"booking:short:{ip}", limit=5, window_seconds=10 * 60)
    limiter.hit(f"booking:day:{ip}", limit=30, window_seconds=24 * 60 * 60)

    booking, created = booking_service.create_booking(db, data)
    if not created:
        response.status_code = 200  # replay of a request we already hold
    return BookingReceipt(reference=booking.reference, status="pending", message=booking_service.RECEIVED_MESSAGE)
