"""Owner-only API. Every route here requires an authenticated owner session
(and a CSRF token for state-changing requests) via the router dependency."""

import datetime as dt
import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import booking_service
from ..database import get_db
from ..errors import ApiError
from ..models import Booking, BookingWindow, MenuCategory, MenuItem
from ..schemas import (
    BookingList,
    BookingNotes,
    BookingOut,
    BookingStatusChange,
    MenuCategoryCreate,
    MenuCategoryOut,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemOut,
    MenuItemUpdate,
    MenuOut,
    SettingsIn,
    SettingsOut,
)
from ..security import require_owner

router = APIRouter(prefix="/api/owner", tags=["owner"], dependencies=[Depends(require_owner)])


@router.get("/bookings", response_model=BookingList)
def list_bookings(
    response: Response,
    status: Literal["pending", "confirmed", "declined", "cancelled"] | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    conditions = []
    if date_from:
        conditions.append(Booking.requested_date >= date_from)
    if date_to:
        conditions.append(Booking.requested_date <= date_to)

    counts = dict.fromkeys(("pending", "confirmed", "declined", "cancelled"), 0)
    counts.update(db.execute(select(Booking.status, func.count()).where(*conditions).group_by(Booking.status)).all())

    if status:
        conditions.append(Booking.status == status)
    total = db.scalar(select(func.count()).select_from(Booking).where(*conditions))
    items = db.scalars(
        select(Booking)
        .where(*conditions)
        .order_by(Booking.requested_at, Booking.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "total": total, "counts": counts}


def _get_booking(db: Session, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise ApiError(404, "not_found", "That booking request does not exist.")
    return booking


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return _get_booking(db, booking_id)


@router.post("/bookings/{booking_id}/status", response_model=BookingOut)
def set_booking_status(booking_id: int, data: BookingStatusChange, db: Session = Depends(get_db)):
    return booking_service.change_status(db, _get_booking(db, booking_id), data.status)


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
def update_booking_notes(booking_id: int, data: BookingNotes, db: Session = Depends(get_db)):
    booking = _get_booking(db, booking_id)
    booking.internal_notes = data.internal_notes
    db.commit()
    return booking


# ---------- Booking settings ----------


def _settings_out(db: Session) -> SettingsOut:
    settings = booking_service.get_booking_settings(db)
    windows = db.scalars(select(BookingWindow).order_by(BookingWindow.weekday, BookingWindow.start_time)).all()
    return SettingsOut(
        booking_enabled=settings.booking_enabled,
        owner_confirmed=settings.owner_confirmed,
        min_party_size=settings.min_party_size,
        max_party_size=settings.max_party_size,
        min_lead_minutes=settings.min_lead_minutes,
        max_advance_days=settings.max_advance_days,
        slot_interval_minutes=settings.slot_interval_minutes,
        windows=windows,
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings_route(db: Session = Depends(get_db)):
    return _settings_out(db)


@router.put("/settings", response_model=SettingsOut)
def update_settings(data: SettingsIn, db: Session = Depends(get_db)):
    settings = booking_service.get_booking_settings(db)
    for field in (
        "booking_enabled",
        "owner_confirmed",
        "min_party_size",
        "max_party_size",
        "min_lead_minutes",
        "max_advance_days",
        "slot_interval_minutes",
    ):
        setattr(settings, field, getattr(data, field))
    for window in db.scalars(select(BookingWindow)).all():
        db.delete(window)
    db.add_all(
        BookingWindow(weekday=w.weekday, start_time=w.start_time, end_time=w.end_time) for w in data.windows
    )
    db.commit()
    return _settings_out(db)


# ---------- Menu ----------


def _slugify(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "category"
    slug, n = base, 2
    while db.scalar(select(MenuCategory.id).where(MenuCategory.slug == slug)) is not None:
        slug, n = f"{base}-{n}", n + 1
    return slug


def _get_category(db: Session, category_id: int) -> MenuCategory:
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise ApiError(422, "validation_error", "Please choose an existing category.", {"category_id": "Unknown category."})
    return category


def _get_item(db: Session, item_id: int) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if item is None:
        raise ApiError(404, "not_found", "That menu item does not exist.")
    return item


@router.get("/menu", response_model=MenuOut)
def owner_menu(db: Session = Depends(get_db)):
    categories = db.scalars(
        select(MenuCategory)
        .options(selectinload(MenuCategory.items))
        .order_by(MenuCategory.sort_order, MenuCategory.id)
    ).all()
    return {"categories": categories}


@router.post("/menu/categories", response_model=MenuCategoryOut, status_code=201)
def create_category(data: MenuCategoryCreate, db: Session = Depends(get_db)):
    category = MenuCategory(slug=_slugify(db, data.name), **data.model_dump())
    db.add(category)
    db.commit()
    return category


@router.patch("/menu/categories/{category_id}", response_model=MenuCategoryOut)
def update_category(category_id: int, data: MenuCategoryUpdate, db: Session = Depends(get_db)):
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise ApiError(404, "not_found", "That category does not exist.")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name", "") is None or changes.get("sort_order", 0) is None:
        raise ApiError(422, "validation_error", "Name and order cannot be empty.")
    for field, value in changes.items():
        setattr(category, field, value)
    db.commit()
    return category


@router.delete("/menu/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise ApiError(404, "not_found", "That category does not exist.")
    if db.scalar(select(func.count()).select_from(MenuItem).where(MenuItem.category_id == category_id)):
        raise ApiError(409, "category_not_empty", "Move or delete the items in this category first.")
    db.delete(category)
    db.commit()


@router.post("/menu/items", response_model=MenuItemOut, status_code=201)
def create_item(data: MenuItemCreate, db: Session = Depends(get_db)):
    _get_category(db, data.category_id)
    item = MenuItem(source="owner", **data.model_dump())
    db.add(item)
    db.commit()
    return item


@router.patch("/menu/items/{item_id}", response_model=MenuItemOut)
def update_item(item_id: int, data: MenuItemUpdate, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    changes = data.model_dump(exclude_unset=True)
    for required in ("category_id", "name", "is_available", "sort_order"):
        if required in changes and changes[required] is None:
            raise ApiError(422, "validation_error", "Please check the highlighted details.", {required: "Cannot be empty."})
    if "category_id" in changes:
        _get_category(db, changes["category_id"])
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    return item


@router.delete("/menu/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    db.delete(_get_item(db, item_id))
    db.commit()
