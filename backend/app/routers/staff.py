"""Staff API, used by the owner and by employees.

Every route checks the signed-in account's role and permissions on the server.
Owners hold every permission; an employee holds only what the owner granted,
read fresh from the database on each request.
"""

import datetime as dt
import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import activity, booking_service
from ..database import get_db
from ..errors import ApiError
from ..models import Account, Booking, BookingDateOverride, BookingWindow, MenuCategory, MenuItem
from ..permissions import BOOKING_STATUSES
from ..schemas import (
    AssignIn,
    CancellationDecision,
    MenuCategoryCreate,
    MenuCategoryOut,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemOut,
    MenuItemUpdate,
    MenuOut,
    PersonRef,
    SettingsIn,
    SettingsOut,
    StaffAlerts,
    StaffBookingList,
    StaffBookingOut,
    StaffNotes,
    StaffStatusChange,
)
from ..security import ensure, require_owner, require_permission, require_staff

router = APIRouter(prefix="/api/staff", tags=["staff"], dependencies=[Depends(require_staff)])


# ---------- bookings ----------


def _scope(actor: Account) -> tuple[Literal["all", "assigned"], list]:
    """Which bookings this account may see, as SQL conditions."""
    if actor.can("bookings.view_all"):
        return "all", []
    if actor.can("bookings.view_assigned"):
        return "assigned", [Booking.assigned_employee_id == actor.id]
    raise ApiError(403, "forbidden", "You don't have permission to view bookings.")


@router.get("/bookings", response_model=StaffBookingList)
def list_bookings(
    response: Response,
    status: Literal["pending", "confirmed", "declined", "cancelled", "checked_in", "completed", "no_show"] | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    cancellation: Literal["pending"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    actor: Account = Depends(require_staff),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    scope, conditions = _scope(actor)
    if date_from:
        conditions.append(Booking.requested_date >= date_from)
    if date_to:
        conditions.append(Booking.requested_date <= date_to)

    counts = dict.fromkeys(BOOKING_STATUSES, 0)
    counts.update(db.execute(select(Booking.status, func.count()).where(*conditions).group_by(Booking.status)).all())

    if status:
        conditions.append(Booking.status == status)
    if cancellation:
        conditions.append(Booking.cancellation_status == "pending")
    total = db.scalar(select(func.count()).select_from(Booking).where(*conditions))
    rows = db.scalars(
        select(Booking).options(selectinload(Booking.assigned_employee)).where(*conditions)
        .order_by(Booking.requested_at, Booking.id).limit(limit).offset(offset)
    ).all()
    return StaffBookingList(items=[booking_service.staff_view(b, actor) for b in rows], total=total, limit=limit,
                            offset=offset, counts=counts, scope=scope)


@router.get("/alerts", response_model=StaffAlerts)
def alerts(response: Response, actor: Account = Depends(require_staff), db: Session = Depends(get_db)):
    """Small payload for the dashboard to poll: how many requests are waiting."""
    response.headers["Cache-Control"] = "no-store"
    _, conditions = _scope(actor)
    pending = [*conditions, Booking.status == "pending"]
    return StaffAlerts(
        pending_count=db.scalar(select(func.count()).select_from(Booking).where(*pending)),
        newest_pending_id=db.scalar(select(func.max(Booking.id)).where(*pending)),
        cancellation_requests=db.scalar(
            select(func.count()).select_from(Booking).where(*conditions, Booking.cancellation_status == "pending")
        ),
    )


@router.get("/bookings/{booking_id}", response_model=StaffBookingOut)
def get_booking(booking_id: int, response: Response, actor: Account = Depends(require_staff), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    booking = db.get(Booking, booking_id)
    if booking is None or not booking_service.can_view(actor, booking):
        raise ApiError(404, "not_found", "That booking request does not exist.")
    return booking_service.staff_view(booking, actor, with_history=True)


@router.post("/bookings/{booking_id}/status", response_model=StaffBookingOut)
def set_status(booking_id: int, data: StaffStatusChange, actor: Account = Depends(require_staff), db: Session = Depends(get_db)):
    booking = booking_service.load_for_update(db, booking_id, actor)
    booking = booking_service.change_status(db, booking, data.status, actor, data.version, data.reason)
    return booking_service.staff_view(booking, actor, with_history=True)


@router.patch("/bookings/{booking_id}", response_model=StaffBookingOut)
def update_notes(booking_id: int, data: StaffNotes, actor: Account = Depends(require_permission("bookings.edit_notes")),
                 db: Session = Depends(get_db)):
    booking = booking_service.load_for_update(db, booking_id, actor)
    return booking_service.staff_view(booking_service.update_notes(db, booking, data.internal_notes, actor, data.version), actor)


@router.post("/bookings/{booking_id}/assign", response_model=StaffBookingOut)
def assign_booking(booking_id: int, data: AssignIn, actor: Account = Depends(require_owner), db: Session = Depends(get_db)):
    employee = None
    if data.employee_id is not None:
        employee = db.scalar(select(Account).where(Account.id == data.employee_id, Account.role == "employee",
                                                   Account.is_active.is_(True)))
        if employee is None:
            raise ApiError(422, "validation_error", "Please choose an active employee.", {"employee_id": "Unknown employee."})
    booking = booking_service.load_for_update(db, booking_id, actor)
    return booking_service.staff_view(booking_service.assign(db, booking, employee, actor, data.version), actor)


@router.post("/bookings/{booking_id}/cancellation", response_model=StaffBookingOut)
def resolve_cancellation(booking_id: int, data: CancellationDecision,
                         actor: Account = Depends(require_permission("bookings.cancel")), db: Session = Depends(get_db)):
    booking = booking_service.load_for_update(db, booking_id, actor)
    booking = booking_service.resolve_cancellation(db, booking, data.decision == "approve", actor, data.version, data.response)
    return booking_service.staff_view(booking, actor, with_history=True)


@router.get("/assignable", response_model=list[PersonRef], dependencies=[Depends(require_owner)])
def assignable_employees(db: Session = Depends(get_db)):
    rows = db.scalars(select(Account).where(Account.role == "employee", Account.is_active.is_(True)).order_by(Account.full_name))
    return [PersonRef(id=a.id, full_name=a.full_name) for a in rows]


# ---------- booking settings ----------

settings_guard = require_permission("booking_settings.manage")


def _settings_out(db: Session) -> SettingsOut:
    settings = booking_service.get_booking_settings(db)
    windows = db.scalars(select(BookingWindow).order_by(BookingWindow.weekday, BookingWindow.start_time)).all()
    overrides = db.scalars(select(BookingDateOverride).order_by(BookingDateOverride.date)).all()
    return SettingsOut(
        booking_enabled=settings.booking_enabled,
        owner_confirmed=settings.owner_confirmed,
        min_party_size=settings.min_party_size,
        max_party_size=settings.max_party_size,
        min_lead_minutes=settings.min_lead_minutes,
        max_advance_days=settings.max_advance_days,
        slot_interval_minutes=settings.slot_interval_minutes,
        windows=windows,
        overrides=overrides,
    )


@router.get("/settings", response_model=SettingsOut, dependencies=[Depends(settings_guard)])
def get_settings_route(db: Session = Depends(get_db)):
    return _settings_out(db)


@router.put("/settings", response_model=SettingsOut)
def update_settings(data: SettingsIn, actor: Account = Depends(settings_guard), db: Session = Depends(get_db)):
    settings = booking_service.get_booking_settings(db)
    # Confirming the provisional rules for real use is the owner's decision alone.
    if data.owner_confirmed != settings.owner_confirmed and actor.role != "owner":
        raise ApiError(403, "forbidden", "Only the owner can confirm the booking rules for real use.")
    for field in ("booking_enabled", "owner_confirmed", "min_party_size", "max_party_size", "min_lead_minutes",
                  "max_advance_days", "slot_interval_minutes"):
        setattr(settings, field, getattr(data, field))
    for row in [*db.scalars(select(BookingWindow)), *db.scalars(select(BookingDateOverride))]:
        db.delete(row)
    db.flush()
    db.add_all(BookingWindow(weekday=w.weekday, start_time=w.start_time, end_time=w.end_time) for w in data.windows)
    db.add_all(BookingDateOverride(date=o.date, is_closed=o.is_closed, start_time=o.start_time, end_time=o.end_time, note=o.note)
               for o in data.overrides)
    activity.record(db, actor, "settings.updated", "booking_settings", 1, booking_enabled=data.booking_enabled,
                    owner_confirmed=data.owner_confirmed)
    db.commit()
    return _settings_out(db)


# ---------- menu (the same rows the public /api/menu serves) ----------

menu_guard = require_permission("menu.manage")

def snapshot_of(name, description, price_npr, addons, sort_order, category_slug) -> dict:
    """The fields a menu import writes, in a comparable form."""
    return {
        "name": name,
        "description": description,
        "price_npr": format(price_npr.normalize(), "f") if price_npr is not None else None,
        "addons": addons or [],
        "sort_order": sort_order,
        "category_slug": category_slug,
    }


def item_snapshot(item: MenuItem, category_slug: str) -> dict:
    return snapshot_of(item.name, item.description, item.price_npr, item.addons, item.sort_order, category_slug)


def _item_out(item: MenuItem, category_slug: str) -> MenuItemOut:
    return MenuItemOut(
        id=item.id, slug=item.slug, category_id=item.category_id, name=item.name, description=item.description,
        is_available=item.is_available, price_npr=item.price_npr, addons=item.addons or [], sort_order=item.sort_order,
        is_published=item.is_published, source=item.source, source_document=item.source_document,
        source_page=item.source_page, review_note=item.review_note,
        edited_since_import=item.imported_snapshot is not None and item.imported_snapshot != item_snapshot(item, category_slug),
    )


def _category_out(category: MenuCategory) -> MenuCategoryOut:
    return MenuCategoryOut(id=category.id, slug=category.slug, name=category.name, tagline=category.tagline,
                           sort_order=category.sort_order, notes=category.notes or [],
                           items=[_item_out(i, category.slug) for i in category.items])


def _slugify(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "category"
    slug, n = base, 2
    while db.scalar(select(MenuCategory.id).where(MenuCategory.slug == slug)) is not None:
        slug, n = f"{base}-{n}", n + 1
    return slug


def _addons(value) -> list[dict]:
    return [{k: (float(v) if k == "price" else v) for k, v in a.items() if v is not None} for a in value]


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


@router.get("/menu", response_model=MenuOut, dependencies=[Depends(menu_guard)])
def staff_menu(db: Session = Depends(get_db)):
    categories = db.scalars(
        select(MenuCategory).options(selectinload(MenuCategory.items)).order_by(MenuCategory.sort_order, MenuCategory.id)
    ).all()
    return MenuOut(categories=[_category_out(c) for c in categories])


@router.post("/menu/categories", response_model=MenuCategoryOut, status_code=201)
def create_category(data: MenuCategoryCreate, actor: Account = Depends(menu_guard), db: Session = Depends(get_db)):
    values = data.model_dump()
    values["notes"] = _addons(data.model_dump(mode="json")["notes"])
    category = MenuCategory(slug=_slugify(db, data.name), **values)
    db.add(category)
    activity.record(db, actor, "menu.category_created", "menu_category", category.slug, name=data.name)
    db.commit()
    return _category_out(category)


@router.patch("/menu/categories/{category_id}", response_model=MenuCategoryOut)
def update_category(category_id: int, data: MenuCategoryUpdate, actor: Account = Depends(menu_guard),
                    db: Session = Depends(get_db)):
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise ApiError(404, "not_found", "That category does not exist.")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name", "") is None or changes.get("sort_order", 0) is None or changes.get("notes", []) is None:
        raise ApiError(422, "validation_error", "Name, order and notes cannot be empty.")
    if "notes" in changes:
        changes["notes"] = _addons(data.model_dump(mode="json")["notes"])
    for field, value in changes.items():
        setattr(category, field, value)
    activity.record(db, actor, "menu.category_updated", "menu_category", category.slug, fields=sorted(changes))
    db.commit()
    return _category_out(category)


@router.delete("/menu/categories/{category_id}", status_code=204)
def delete_category(category_id: int, actor: Account = Depends(menu_guard), db: Session = Depends(get_db)):
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise ApiError(404, "not_found", "That category does not exist.")
    if db.scalar(select(func.count()).select_from(MenuItem).where(MenuItem.category_id == category_id)):
        raise ApiError(409, "category_not_empty", "Move or delete the items in this category first.")
    activity.record(db, actor, "menu.category_deleted", "menu_category", category.slug, name=category.name)
    db.delete(category)
    db.commit()


@router.post("/menu/items", response_model=MenuItemOut, status_code=201)
def create_item(data: MenuItemCreate, actor: Account = Depends(menu_guard), db: Session = Depends(get_db)):
    category = _get_category(db, data.category_id)
    values = data.model_dump()
    values["addons"] = _addons(data.model_dump(mode="json")["addons"])
    item = MenuItem(source="owner", **values)
    db.add(item)
    activity.record(db, actor, "menu.item_created", "menu_item", None, name=data.name)
    db.commit()
    return _item_out(item, category.slug)


@router.patch("/menu/items/{item_id}", response_model=MenuItemOut)
def update_item(item_id: int, data: MenuItemUpdate, actor: Account = Depends(menu_guard), db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    changes = data.model_dump(exclude_unset=True)
    for required in ("category_id", "name", "is_available", "is_published", "sort_order", "addons"):
        if required in changes and changes[required] is None:
            raise ApiError(422, "validation_error", "Please check the highlighted details.", {required: "Cannot be empty."})
    if "category_id" in changes:
        _get_category(db, changes["category_id"])
    if "addons" in changes:
        changes["addons"] = _addons(data.model_dump(mode="json")["addons"])
    for field, value in changes.items():
        setattr(item, field, value)
    activity.record(db, actor, "menu.item_updated", "menu_item", item.id, name=item.name, fields=sorted(changes))
    db.commit()
    db.refresh(item)
    return _item_out(item, item.category.slug)


@router.delete("/menu/items/{item_id}", status_code=204)
def delete_item(item_id: int, actor: Account = Depends(menu_guard), db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    activity.record(db, actor, "menu.item_deleted", "menu_item", item.id, name=item.name)
    db.delete(item)
    db.commit()
