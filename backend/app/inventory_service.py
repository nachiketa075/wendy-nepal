"""Staff inventory: items and their stock movements.

Rules kept here, in one place:

* An item's quantity changes only in `record_movement` (and once in
  `create_item` for opening stock), always together with an
  InventoryMovement row in the same transaction.
* The item row is locked (SELECT ... FOR UPDATE) before its stock is read, so
  two people taking stock out at once cannot both spend the same units, and
  stock can never go below zero.
* Every movement carries an idempotency key from the client; a retry or a
  double-click with the same key returns the movement already recorded.
* A stock count (adjustment) or an edit of item details must name the item
  version it was based on; if the item changed since, nothing is written.
* The actor always comes from the signed-in session.
"""

import hashlib
import json
import logging
from decimal import Decimal

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import activity
from .errors import ApiError
from .models import Account, InventoryItem, InventoryMovement
from .schemas import InventoryItemCreate, InventoryItemOut, InventoryItemUpdate, InventoryMovementIn, InventoryMovementOut

logger = logging.getLogger("wendy.inventory")

UNIT_WORDS = {"kg": "kg", "litre": "litres", "piece": "pieces"}


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(422, "validation_error", "Please check the highlighted details.", {field: message})


def _request_hash(actor: Account, **payload) -> str:
    payload["actor_id"] = actor.id
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _check_whole(unit: str, value: Decimal | None, field: str) -> None:
    if unit == "piece" and value is not None and value != value.to_integral_value():
        raise _invalid(field, "Items counted in pieces need a whole number.")


def _show(value: Decimal, unit: str) -> str:
    text = format(value, "f")
    text = text.rstrip("0").rstrip(".") if "." in text else text
    return f"{text} {UNIT_WORDS[unit]}"


def is_low(item: InventoryItem) -> bool:
    return item.is_active and item.low_stock_threshold is not None and item.quantity <= item.low_stock_threshold


def item_out(item: InventoryItem, has_movements: bool) -> InventoryItemOut:
    return InventoryItemOut(
        id=item.id, name=item.name, category=item.category, unit=item.unit, quantity=item.quantity,
        low_stock_threshold=item.low_stock_threshold, is_low=is_low(item), is_active=item.is_active,
        version=item.version, has_movements=has_movements, created_at=item.created_at, updated_at=item.updated_at,
    )


def movement_out(movement: InventoryMovement, item: InventoryItem) -> InventoryMovementOut:
    return InventoryMovementOut(
        id=movement.id, item_id=item.id, item_name=item.name, unit=item.unit, kind=movement.kind,
        quantity_change=movement.quantity_change, balance_after=movement.balance_after, reason=movement.reason,
        actor_name=movement.actor_name, actor_role=movement.actor_role, created_at=movement.created_at,
    )


def has_movements(db: Session, item_id: int) -> bool:
    return bool(db.scalar(select(exists().where(InventoryMovement.item_id == item_id))))


def _name_taken(db: Session, name: str, except_id: int | None = None) -> bool:
    query = select(InventoryItem.id).where(func.lower(InventoryItem.name) == name.lower())
    if except_id is not None:
        query = query.where(InventoryItem.id != except_id)
    return db.scalar(query) is not None


NAME_TAKEN = "An item with this name already exists. Search for it, or choose another name."


def _lock_item(db: Session, item_id: int) -> InventoryItem:
    item = db.scalar(
        select(InventoryItem).where(InventoryItem.id == item_id).with_for_update().execution_options(populate_existing=True)
    )
    if item is None:
        db.rollback()
        raise ApiError(404, "not_found", "That inventory item does not exist.")
    return item


def _replay(db: Session, key: str, request_hash: str) -> InventoryMovement | None:
    """The movement already recorded under this key, if any."""
    movement = db.scalar(select(InventoryMovement).where(InventoryMovement.idempotency_key == key))
    if movement is not None and movement.request_hash != request_hash:
        db.rollback()
        raise ApiError(409, "idempotency_conflict",
                       "This submission was already used for a different stock change. Please reload and try again.")
    return movement


def _movement(item: InventoryItem, actor: Account, kind: str, change: Decimal, reason: str | None,
              key: str, request_hash: str) -> InventoryMovement:
    return InventoryMovement(
        item=item, kind=kind, quantity_change=change, balance_after=item.quantity, reason=reason,
        actor_id=actor.id, actor_role=actor.role, actor_name=actor.full_name,
        idempotency_key=key, request_hash=request_hash,
    )


def create_item(db: Session, data: InventoryItemCreate, actor: Account) -> tuple[InventoryItem, bool]:
    """Create an item; opening stock, if any, is recorded as an "opening" movement.
    Returns (item, created)."""
    opening = data.opening_quantity or Decimal(0)
    request_hash = _request_hash(actor, op="create", **data.model_dump(mode="json", exclude={"idempotency_key"}))
    if opening > 0:
        previous = _replay(db, data.idempotency_key, request_hash)
        if previous is not None:
            return previous.item, False
    _check_whole(data.unit, data.low_stock_threshold, "low_stock_threshold")
    _check_whole(data.unit, data.opening_quantity, "opening_quantity")
    if _name_taken(db, data.name):
        raise ApiError(409, "name_taken", "Please check the highlighted details.", {"name": NAME_TAKEN})

    item = InventoryItem(name=data.name, category=data.category, unit=data.unit, quantity=opening,
                         low_stock_threshold=data.low_stock_threshold)
    db.add(item)
    if opening > 0:
        db.add(_movement(item, actor, "opening", opening, "Opening stock", data.idempotency_key, request_hash))
    db.flush()
    activity.record(db, actor, "inventory.item_created", "inventory_item", item.id, name=item.name,
                    opening=_show(opening, item.unit))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = _replay(db, data.idempotency_key, request_hash) if opening > 0 else None
        if previous is not None:  # a simultaneous retry of the same submission won
            return previous.item, False
        raise ApiError(409, "name_taken", "Please check the highlighted details.", {"name": NAME_TAKEN}) from None
    logger.info("inventory item created id=%s", item.id)
    return item, True


def update_item(db: Session, item_id: int, data: InventoryItemUpdate, actor: Account) -> InventoryItem:
    """Edit details or archive/restore. Never touches the quantity."""
    item = _lock_item(db, item_id)
    if item.version != data.version:
        db.rollback()
        raise ApiError(409, "stale_update", "Someone else changed this item a moment ago. It has been reloaded; please check and try again.")
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if k != "version"}
    for field in ("name", "category", "unit", "is_active"):
        if field in changes and changes[field] is None:
            db.rollback()
            raise _invalid(field, "Cannot be empty.")
    changes = {k: v for k, v in changes.items() if getattr(item, k) != v}

    unit = changes.get("unit", item.unit)
    if "unit" in changes and has_movements(db, item.id):
        db.rollback()
        raise ApiError(409, "unit_locked", "Please check the highlighted details.",
                       {"unit": "The unit cannot change once stock has been recorded. Archive this item and add a new one instead."})
    threshold = changes.get("low_stock_threshold", item.low_stock_threshold)
    try:
        _check_whole(unit, threshold, "low_stock_threshold")
    except ApiError:
        db.rollback()
        raise
    if "name" in changes and _name_taken(db, changes["name"], item.id):
        db.rollback()
        raise ApiError(409, "name_taken", "Please check the highlighted details.", {"name": NAME_TAKEN})
    if not changes:
        db.rollback()
        return item

    for field, value in changes.items():
        setattr(item, field, value)
    item.version += 1
    if "is_active" in changes:
        activity.record(db, actor, "inventory.item_restored" if item.is_active else "inventory.item_archived",
                        "inventory_item", item.id, name=item.name)
    details = sorted(set(changes) - {"is_active"})
    if details:
        activity.record(db, actor, "inventory.item_updated", "inventory_item", item.id, name=item.name, fields=details)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "name_taken", "Please check the highlighted details.", {"name": NAME_TAKEN}) from None
    return item


def record_movement(db: Session, item_id: int, data: InventoryMovementIn,
                    actor: Account) -> tuple[InventoryItem, InventoryMovement, bool]:
    """Stock in, stock out or a counted correction, applied atomically.
    Returns (item, movement, created)."""
    request_hash = _request_hash(actor, op="movement", item_id=item_id,
                                 **data.model_dump(mode="json", exclude={"idempotency_key"}))
    item = _lock_item(db, item_id)
    previous = _replay(db, data.idempotency_key, request_hash)
    if previous is not None:
        db.rollback()
        return item, previous, False

    def refuse(error: ApiError):
        db.rollback()
        raise error

    if not item.is_active:
        refuse(ApiError(409, "item_archived", "This item is archived. Restore it before recording stock."))
    if item.unit == "piece" and data.quantity != data.quantity.to_integral_value():
        refuse(_invalid("quantity", "Items counted in pieces need a whole number."))

    if data.kind == "adjustment":
        if not data.reason:
            refuse(_invalid("reason", "Say why the stock is being corrected, for example “Weekly count”."))
        if data.version is None:
            refuse(_invalid("version", "Reload the item and count again."))
        if data.version != item.version:
            refuse(ApiError(409, "stale_update",
                            "The stock changed since you opened this item. It has been reloaded; please count again."))
        change = data.quantity - item.quantity
        new_balance = data.quantity
    else:
        if data.quantity <= 0:
            refuse(_invalid("quantity", "Enter an amount more than 0."))
        change = data.quantity if data.kind == "stock_in" else -data.quantity
        new_balance = item.quantity + change
        if new_balance < 0:
            refuse(ApiError(409, "insufficient_stock", "Please check the highlighted details.",
                            {"quantity": f"Only {_show(item.quantity, item.unit)} in stock. Stock cannot go below zero."}))
        if new_balance > Decimal("999999999.999"):
            refuse(_invalid("quantity", "That would make the stock too large to record."))

    item.quantity = new_balance
    item.version += 1
    movement = _movement(item, actor, data.kind, change, data.reason, data.idempotency_key, request_hash)
    db.add(movement)
    if data.kind == "adjustment":
        activity.record(db, actor, "inventory.stock_corrected", "inventory_item", item.id, name=item.name,
                        change=_show(change, item.unit), balance=_show(new_balance, item.unit), reason=data.reason)
    try:
        db.commit()
    except IntegrityError:
        # Only possible if the same key was used at the same moment for another item.
        db.rollback()
        previous = _replay(db, data.idempotency_key, request_hash)
        if previous is None:
            raise
        return previous.item, previous, False
    logger.info("inventory movement recorded item=%s kind=%s", item.id, data.kind)
    return item, movement, True
