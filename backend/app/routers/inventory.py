"""Inventory API for the owner and for employees the owner has allowed.

Every route needs `inventory.view`; changes also need `inventory.manage_items`
(item details) or `inventory.adjust_stock` (stock movements). Customers and
visitors are refused before any inventory data is read. Nothing here is used by
the public site or the public menu.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import inventory_service
from ..database import get_db
from ..errors import ApiError
from ..models import Account, InventoryItem, InventoryMovement
from ..rate_limit import limiter
from ..schemas import (
    InventoryCategory,
    InventoryItemCreate,
    InventoryItemList,
    InventoryItemOut,
    InventoryItemUpdate,
    InventoryMovementIn,
    InventoryMovementList,
    InventoryMovementResult,
)
from ..security import ensure, require_permission

view_guard = require_permission("inventory.view")
router = APIRouter(prefix="/api/staff/inventory", tags=["inventory"], dependencies=[Depends(view_guard)])


def _writer(permission: str):
    """inventory.view (checked first) plus the permission for this change."""

    def dependency(account: Account = Depends(view_guard)) -> Account:
        ensure(account, permission)
        # Generous for people, but stops a stuck script or a runaway client.
        limiter.hit(f"inventory:write:{account.id}", limit=300, window_seconds=15 * 60)
        return account

    return dependency


manage_guard = _writer("inventory.manage_items")
stock_guard = _writer("inventory.adjust_stock")


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _low(conditions: list) -> list:
    return [*conditions, InventoryItem.is_active.is_(True), InventoryItem.low_stock_threshold.is_not(None),
            InventoryItem.quantity <= InventoryItem.low_stock_threshold]


@router.get("/items", response_model=InventoryItemList)
def list_items(
    response: Response,
    search: str | None = Query(None, max_length=120),
    category: InventoryCategory | None = None,
    status: Literal["active", "archived", "all"] = "active",
    low_stock: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    conditions = []
    if search and search.strip():
        conditions.append(InventoryItem.name.ilike(_like(search.strip()), escape="\\"))
    if category:
        conditions.append(InventoryItem.category == category)
    if status != "all":
        conditions.append(InventoryItem.is_active.is_(status == "active"))
    if low_stock:
        conditions = _low(conditions)

    total = db.scalar(select(func.count()).select_from(InventoryItem).where(*conditions))
    rows = db.scalars(
        select(InventoryItem).where(*conditions).order_by(func.lower(InventoryItem.name), InventoryItem.id)
        .limit(limit).offset(offset)
    ).all()
    with_history = set(db.scalars(
        select(InventoryMovement.item_id).where(InventoryMovement.item_id.in_([r.id for r in rows])).distinct()
    )) if rows else set()
    return InventoryItemList(
        items=[inventory_service.item_out(r, r.id in with_history) for r in rows],
        total=total, limit=limit, offset=offset,
        low_stock_count=db.scalar(select(func.count()).select_from(InventoryItem).where(*_low([]))),
    )


def _get_item(db: Session, item_id: int) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise ApiError(404, "not_found", "That inventory item does not exist.")
    return item


@router.get("/items/{item_id}", response_model=InventoryItemOut)
def get_item(item_id: int, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    item = _get_item(db, item_id)
    return inventory_service.item_out(item, inventory_service.has_movements(db, item.id))


@router.post("/items", response_model=InventoryItemOut, status_code=201)
def create_item(data: InventoryItemCreate, response: Response, actor: Account = Depends(manage_guard),
                db: Session = Depends(get_db)):
    item, created = inventory_service.create_item(db, data, actor)
    if not created:
        response.status_code = 200  # replay of a submission already recorded
    return inventory_service.item_out(item, inventory_service.has_movements(db, item.id))


@router.patch("/items/{item_id}", response_model=InventoryItemOut)
def update_item(item_id: int, data: InventoryItemUpdate, actor: Account = Depends(manage_guard),
                db: Session = Depends(get_db)):
    item = inventory_service.update_item(db, item_id, data, actor)
    return inventory_service.item_out(item, inventory_service.has_movements(db, item.id))


@router.post("/items/{item_id}/movements", response_model=InventoryMovementResult, status_code=201)
def record_movement(item_id: int, data: InventoryMovementIn, response: Response, actor: Account = Depends(stock_guard),
                    db: Session = Depends(get_db)):
    item, movement, created = inventory_service.record_movement(db, item_id, data, actor)
    if not created:
        response.status_code = 200
    return InventoryMovementResult(item=inventory_service.item_out(item, True),
                                   movement=inventory_service.movement_out(movement, movement.item))


@router.get("/movements", response_model=InventoryMovementList)
def list_movements(
    response: Response,
    item_id: int | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Stock history, newest first. Read-only: there is no route to edit or delete a movement."""
    response.headers["Cache-Control"] = "no-store"
    conditions = [InventoryMovement.item_id == item_id] if item_id is not None else []
    total = db.scalar(select(func.count()).select_from(InventoryMovement).where(*conditions))
    rows = db.execute(
        select(InventoryMovement, InventoryItem).join(InventoryItem, InventoryMovement.item_id == InventoryItem.id)
        .where(*conditions).order_by(InventoryMovement.id.desc()).limit(limit).offset(offset)
    ).all()
    return InventoryMovementList(items=[inventory_service.movement_out(m, i) for m, i in rows],
                                 total=total, limit=limit, offset=offset)
