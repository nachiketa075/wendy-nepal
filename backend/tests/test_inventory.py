"""Staff-only inventory: access control, stock rules, idempotency, concurrency and history."""

import os
import threading
import uuid
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app import inventory_service
from app.database import SessionLocal, engine
from app.errors import ApiError
from app.main import app
from app.models import Account
from app.schemas import InventoryMovementIn

from .conftest import OWNER_EMAIL, employee_client, make_account, make_booking, sign_in

VIEW, MANAGE, ADJUST = "inventory.view", "inventory.manage_items", "inventory.adjust_stock"
BASE = "/api/staff/inventory"


def key() -> str:
    return uuid.uuid4().hex


def new_item(client: TestClient, **overrides) -> dict:
    body = {"name": "Banana", "category": "fruit_veg", "unit": "kg", "idempotency_key": key(), **overrides}
    response = client.post(f"{BASE}/items", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def move(client: TestClient, item_id: int, kind: str, quantity, **extra):
    return client.post(f"{BASE}/items/{item_id}/movements",
                       json={"kind": kind, "quantity": quantity, "idempotency_key": extra.pop("idempotency_key", key()), **extra})


def item(client: TestClient, item_id: int) -> dict:
    return client.get(f"{BASE}/items/{item_id}").json()


def history(client: TestClient, item_id: int | None = None, **params) -> dict:
    query = {"item_id": item_id, **params} if item_id else params
    response = client.get(f"{BASE}/movements", params=query)
    assert response.status_code == 200, response.text
    return response.json()


# ---------- who can reach inventory ----------


def every_route(item_id: int) -> list[tuple[str, str, dict | None]]:
    return [
        ("GET", f"{BASE}/items", None),
        ("GET", f"{BASE}/items/{item_id}", None),
        ("GET", f"{BASE}/movements", None),
        ("POST", f"{BASE}/items", {"name": "Cups", "category": "packaging", "unit": "piece", "idempotency_key": key()}),
        ("PATCH", f"{BASE}/items/{item_id}", {"version": 1, "name": "Changed"}),
        ("POST", f"{BASE}/items/{item_id}/movements", {"kind": "stock_in", "quantity": "1", "idempotency_key": key()}),
    ]


def test_visitors_and_customers_cannot_reach_any_inventory_route(owner_client, client, customer_client):
    banana = new_item(owner_client, opening_quantity="3")
    for method, path, body in every_route(banana["id"]):
        anonymous = client.request(method, path, json=body)
        assert anonymous.status_code == 401, (method, path, anonymous.text)
        assert "Banana" not in anonymous.text
        refused = customer_client.request(method, path, json=body)
        assert refused.status_code == 403, (method, path, refused.text)
        assert refused.json()["error"]["code"] == "forbidden" and "Banana" not in refused.text
    # Nothing changed.
    assert item(owner_client, banana["id"])["quantity"] == "3"
    assert history(owner_client)["total"] == 1


def test_inventory_never_appears_in_public_responses(owner_client, client):
    new_item(owner_client, name="Secret Supplier Mango Pulp", opening_quantity="7")
    for path in ("/api/menu", "/api/booking/config", "/api/health"):
        assert "Mango Pulp" not in client.get(path).text
    # Every inventory route sits under the staff prefix, behind the inventory guard.
    inventory_paths = [path for path in app.openapi()["paths"] if "inventory" in path]
    assert inventory_paths and all(path.startswith(f"{BASE}/") for path in inventory_paths)


def test_employee_without_inventory_permissions_is_refused(owner_client):
    banana = new_item(owner_client)
    employee = employee_client(["bookings.view_all", "menu.manage", "booking_settings.manage"])
    for method, path, body in every_route(banana["id"]):
        assert employee.request(method, path, json=body).status_code == 403, (method, path)


@pytest.mark.parametrize("permissions,can_view,can_manage,can_adjust", [
    ([VIEW], True, False, False),
    ([VIEW, MANAGE], True, True, False),
    ([VIEW, ADJUST], True, False, True),
    ([VIEW, MANAGE, ADJUST], True, True, True),
    # Stored without inventory.view (for example written before the rule existed): still refused everywhere.
    ([MANAGE, ADJUST], False, False, False),
])
def test_employee_permission_combinations(owner_client, permissions, can_view, can_manage, can_adjust):
    banana = new_item(owner_client, opening_quantity="10")
    employee = employee_client(permissions)

    def ok(response, allowed):
        if allowed:
            assert response.status_code in (200, 201), response.text
        else:
            assert response.status_code == 403, response.text

    ok(employee.get(f"{BASE}/items"), can_view)
    ok(employee.get(f"{BASE}/movements"), can_view)
    ok(employee.post(f"{BASE}/items", json={"name": "Milk", "category": "dairy", "unit": "litre", "idempotency_key": key()}), can_manage)
    ok(employee.patch(f"{BASE}/items/{banana['id']}", json={"version": banana["version"], "low_stock_threshold": "2"}), can_manage)
    ok(move(employee, banana["id"], "stock_out", "1"), can_adjust)


def test_owner_has_full_access(owner_client):
    milk = new_item(owner_client, name="Milk", category="dairy", unit="litre", opening_quantity="12.5", low_stock_threshold="5")
    assert move(owner_client, milk["id"], "stock_out", "8").status_code == 201
    corrected = move(owner_client, milk["id"], "adjustment", "4", reason="Morning count", version=item(owner_client, milk["id"])["version"])
    assert corrected.status_code == 201 and corrected.json()["item"]["is_low"] is True
    archived = owner_client.patch(f"{BASE}/items/{milk['id']}", json={"version": corrected.json()["item"]["version"], "is_active": False})
    assert archived.status_code == 200 and archived.json()["is_active"] is False


def test_revoking_permissions_and_deactivating_apply_to_the_next_request(owner_client):
    banana = new_item(owner_client, opening_quantity="10")
    employee = employee_client([VIEW, ADJUST])
    employee_id = owner_client.get("/api/owner/employees").json()[0]["id"]
    assert move(employee, banana["id"], "stock_out", "1").status_code == 201

    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": [VIEW]})
    assert move(employee, banana["id"], "stock_out", "1").status_code == 403
    assert employee.get(f"{BASE}/items").status_code == 200

    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": []})
    assert employee.get(f"{BASE}/items").status_code == 403

    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": [VIEW]})
    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"is_active": False})
    assert employee.get(f"{BASE}/items").status_code == 401
    assert item(owner_client, banana["id"])["quantity"] == "9"


def test_permission_dependencies_are_enforced_and_nothing_is_granted_by_default(owner_client):
    listed = {p["key"]: p for p in owner_client.get("/api/owner/permissions").json()}
    assert listed[MANAGE]["requires"] == VIEW and listed[ADJUST]["requires"] == VIEW and listed[VIEW]["requires"] is None

    created = owner_client.post("/api/owner/employees", json={"email": "new@example.com", "full_name": "New Person"})
    assert created.status_code == 201 and created.json()["employee"]["permissions"] == []

    refused = owner_client.post("/api/owner/employees", json={"email": "x@example.com", "full_name": "X Person", "permissions": [ADJUST]})
    assert refused.status_code == 422 and "permissions" in refused.json()["error"]["fields"]

    employee_id = created.json()["employee"]["id"]
    refused = owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": [MANAGE]})
    assert refused.status_code == 422
    assert owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": [VIEW, MANAGE]}).status_code == 200


def test_writes_need_the_csrf_token(owner_client):
    banana = new_item(owner_client)
    del owner_client.headers["X-CSRF-Token"]
    refused = move(owner_client, banana["id"], "stock_in", "1")
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "csrf_failed"


def test_actor_comes_from_the_session_not_the_request(owner_client):
    banana = new_item(owner_client)
    employee = employee_client([VIEW, ADJUST], "worker@example.com")
    forged = move(employee, banana["id"], "stock_in", "1", actor_id=1, actor_name="The Owner")
    assert forged.status_code == 422
    recorded = move(employee, banana["id"], "stock_in", "2").json()["movement"]
    assert recorded["actor_name"] == "Test Employee" and recorded["actor_role"] == "employee"


# ---------- quantities ----------


@pytest.mark.parametrize("bad", ["1.2345", "abc", "-1", "NaN", "Infinity", "1e12", "", True, [1], {"a": 1}])
def test_invalid_quantities_are_refused(owner_client, bad):
    banana = new_item(owner_client, opening_quantity="5")
    response = move(owner_client, banana["id"], "stock_in", bad)
    assert response.status_code == 422, response.text
    assert "quantity" in response.json()["error"]["fields"]
    assert item(owner_client, banana["id"])["quantity"] == "5"


def test_decimals_are_exact(owner_client):
    banana = new_item(owner_client, opening_quantity=0.1)  # a JSON number
    move(owner_client, banana["id"], "stock_in", 0.2)
    move(owner_client, banana["id"], "stock_in", "0.125")
    assert item(owner_client, banana["id"])["quantity"] == "0.425"  # not 0.42500000000000004
    with engine.connect() as conn:
        assert conn.execute(text("SELECT quantity FROM inventory_items")).scalar_one() == Decimal("0.425")


def test_pieces_must_be_whole_numbers(owner_client):
    cups = new_item(owner_client, name="Cups 12oz", category="packaging", unit="piece", opening_quantity="100")
    assert move(owner_client, cups["id"], "stock_out", "1.5").status_code == 422
    assert move(owner_client, cups["id"], "stock_out", "2.000").status_code == 201  # whole, written with decimals
    assert owner_client.post(f"{BASE}/items", json={"name": "Lids", "category": "packaging", "unit": "piece",
                                                    "opening_quantity": "0.5", "idempotency_key": key()}).status_code == 422
    assert owner_client.patch(f"{BASE}/items/{cups['id']}", json={"version": item(owner_client, cups["id"])["version"],
                                                                   "low_stock_threshold": "2.5"}).status_code == 422
    assert item(owner_client, cups["id"])["quantity"] == "98"


def test_stock_cannot_go_negative(owner_client):
    banana = new_item(owner_client, opening_quantity="2.5")
    refused = move(owner_client, banana["id"], "stock_out", "2.501")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "insufficient_stock"
    assert "2.5 kg" in refused.json()["error"]["fields"]["quantity"]
    assert move(owner_client, banana["id"], "adjustment", "-1", reason="count", version=banana["version"]).status_code == 422
    assert move(owner_client, banana["id"], "stock_out", "0").status_code == 422
    assert move(owner_client, banana["id"], "stock_out", "2.5").status_code == 201
    assert item(owner_client, banana["id"])["quantity"] == "0"
    assert history(owner_client, banana["id"])["total"] == 2


def test_database_refuses_negative_stock_even_without_the_app():
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO inventory_items (name, category, unit) VALUES ('Raw', 'other', 'kg')"))
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("UPDATE inventory_items SET quantity = -1"))


# ---------- items ----------


def test_opening_stock_is_a_movement_and_zero_opening_records_none(owner_client):
    milk = new_item(owner_client, name="Milk", category="dairy", unit="litre", opening_quantity="6")
    entries = history(owner_client, milk["id"])["items"]
    assert [(e["kind"], e["quantity_change"], e["balance_after"]) for e in entries] == [("opening", "6", "6")]
    assert milk["has_movements"] is True

    sugar = new_item(owner_client, name="Sugar", category="dry_goods")
    assert sugar["quantity"] == "0" and sugar["has_movements"] is False
    assert history(owner_client, sugar["id"])["total"] == 0


def test_editing_details_never_changes_stock(owner_client):
    banana = new_item(owner_client, opening_quantity="4")
    smuggled = owner_client.patch(f"{BASE}/items/{banana['id']}", json={"version": banana["version"], "quantity": "100"})
    assert smuggled.status_code == 422
    edited = owner_client.patch(f"{BASE}/items/{banana['id']}",
                                json={"version": banana["version"], "name": "Bananas (ripe)", "category": "other", "low_stock_threshold": "1"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["quantity"] == "4" and edited.json()["name"] == "Bananas (ripe)"
    assert history(owner_client, banana["id"])["total"] == 1


def test_unit_is_fixed_once_stock_is_recorded(owner_client):
    sugar = new_item(owner_client, name="Sugar", category="dry_goods")
    changed = owner_client.patch(f"{BASE}/items/{sugar['id']}", json={"version": sugar["version"], "unit": "piece"})
    assert changed.status_code == 200 and changed.json()["unit"] == "piece"
    move(owner_client, sugar["id"], "stock_in", "3")
    locked = owner_client.patch(f"{BASE}/items/{sugar['id']}", json={"version": item(owner_client, sugar["id"])["version"], "unit": "kg"})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "unit_locked"


def test_stale_edit_is_refused(owner_client):
    banana = new_item(owner_client)
    assert owner_client.patch(f"{BASE}/items/{banana['id']}", json={"version": banana["version"], "name": "A"}).status_code == 200
    stale = owner_client.patch(f"{BASE}/items/{banana['id']}", json={"version": banana["version"], "name": "B"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_update"
    assert item(owner_client, banana["id"])["name"] == "A"


def test_names_are_unique_ignoring_case(owner_client):
    new_item(owner_client, name="Coffee beans", category="coffee_tea")
    duplicate = owner_client.post(f"{BASE}/items", json={"name": "COFFEE BEANS", "category": "coffee_tea", "unit": "kg", "idempotency_key": key()})
    assert duplicate.status_code == 409 and "name" in duplicate.json()["error"]["fields"]


def test_archive_keeps_history_and_blocks_movements(owner_client):
    banana = new_item(owner_client, opening_quantity="3")
    archived = owner_client.patch(f"{BASE}/items/{banana['id']}", json={"version": banana["version"], "is_active": False}).json()
    assert move(owner_client, banana["id"], "stock_in", "1").json()["error"]["code"] == "item_archived"
    assert history(owner_client, banana["id"])["total"] == 1
    assert owner_client.get(f"{BASE}/items").json()["total"] == 0
    assert owner_client.get(f"{BASE}/items", params={"status": "archived"}).json()["items"][0]["id"] == banana["id"]
    assert owner_client.delete(f"{BASE}/items/{banana['id']}").status_code == 405
    restored = owner_client.patch(f"{BASE}/items/{banana['id']}", json={"version": archived["version"], "is_active": True})
    assert restored.status_code == 200 and move(owner_client, banana["id"], "stock_in", "1").status_code == 201


def test_search_category_and_low_stock_filters(owner_client):
    new_item(owner_client, name="Banana", opening_quantity="1", low_stock_threshold="2")
    new_item(owner_client, name="Mango 50% pulp", opening_quantity="9", low_stock_threshold="2")
    new_item(owner_client, name="Whole milk", category="dairy", unit="litre", opening_quantity="2", low_stock_threshold="2")
    new_item(owner_client, name="Paper cups", category="packaging", unit="piece")

    names = lambda **p: [i["name"] for i in owner_client.get(f"{BASE}/items", params=p).json()["items"]]  # noqa: E731
    assert names(search="MILK") == ["Whole milk"]
    assert names(search="50%") == ["Mango 50% pulp"]  # % is matched literally
    assert names(search="_") == []
    assert names(category="fruit_veg") == ["Banana", "Mango 50% pulp"]
    assert names(low_stock="true") == ["Banana", "Whole milk"]  # at or below the threshold
    listing = owner_client.get(f"{BASE}/items", params={"limit": 2}).json()
    assert listing["total"] == 4 and len(listing["items"]) == 2 and listing["low_stock_count"] == 2
    assert owner_client.get(f"{BASE}/items", params={"category": "weapons"}).status_code == 422


# ---------- duplicates and history ----------


def test_retried_movement_is_recorded_once(owner_client):
    banana = new_item(owner_client, opening_quantity="10")
    same = key()
    first = move(owner_client, banana["id"], "stock_out", "3", idempotency_key=same)
    again = move(owner_client, banana["id"], "stock_out", "3", idempotency_key=same)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["movement"]["id"] == first.json()["movement"]["id"]
    assert item(owner_client, banana["id"])["quantity"] == "7"

    changed = move(owner_client, banana["id"], "stock_out", "4", idempotency_key=same)
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "idempotency_conflict"
    assert history(owner_client, banana["id"])["total"] == 2


def test_retried_create_with_opening_stock_creates_one_item(owner_client):
    body = {"name": "Oat milk", "category": "dairy", "unit": "litre", "opening_quantity": "4", "idempotency_key": key()}
    first = owner_client.post(f"{BASE}/items", json=body)
    again = owner_client.post(f"{BASE}/items", json=body)
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert history(owner_client)["total"] == 1


def test_adjustment_needs_reason_and_current_version(owner_client):
    banana = new_item(owner_client, opening_quantity="5")
    assert move(owner_client, banana["id"], "adjustment", "4", version=banana["version"]).status_code == 422
    assert move(owner_client, banana["id"], "adjustment", "4", reason="Count").status_code == 422
    move(owner_client, banana["id"], "stock_in", "1")  # someone else changes the stock meanwhile
    stale = move(owner_client, banana["id"], "adjustment", "4", reason="Count", version=banana["version"])
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_update"
    fresh = item(owner_client, banana["id"])
    done = move(owner_client, banana["id"], "adjustment", "4", reason="Weekly count: 2 kg spoiled", version=fresh["version"])
    assert done.status_code == 201
    assert done.json()["movement"]["quantity_change"] == "-2" and done.json()["movement"]["balance_after"] == "4"
    log = owner_client.get("/api/owner/activity").json()["items"]
    assert log[0]["action"] == "inventory.stock_corrected" and log[0]["detail"]["reason"] == "Weekly count: 2 kg spoiled"


def test_history_is_accurate_and_paginated(owner_client):
    banana = new_item(owner_client, opening_quantity="10")
    employee = employee_client([VIEW, ADJUST], "worker@example.com")
    move(owner_client, banana["id"], "stock_in", "2.5", reason="Market delivery")
    move(employee, banana["id"], "stock_out", "4")
    move(employee, banana["id"], "stock_out", "0.75", reason="Smoothies")
    move(owner_client, banana["id"], "adjustment", "7", reason="Count", version=item(owner_client, banana["id"])["version"])
    new_item(owner_client, name="Other", opening_quantity="1")

    entries = history(owner_client, banana["id"])["items"]
    assert [(e["kind"], e["quantity_change"], e["balance_after"], e["actor_name"]) for e in entries] == [
        ("adjustment", "-0.75", "7", "Test Owner"),
        ("stock_out", "-0.75", "7.75", "Test Employee"),
        ("stock_out", "-4", "8.5", "Test Employee"),
        ("stock_in", "2.5", "12.5", "Test Owner"),
        ("opening", "10", "10", "Test Owner"),
    ]
    # Every balance follows from the one before it, and the last one is the item's stock.
    running = Decimal(0)
    for entry in reversed(entries):
        running += Decimal(entry["quantity_change"])
        assert Decimal(entry["balance_after"]) == running
    assert Decimal(item(owner_client, banana["id"])["quantity"]) == running
    assert entries[3]["reason"] == "Market delivery" and entries[0]["created_at"]

    page = history(owner_client, banana["id"], limit=2, offset=2)
    assert page["total"] == 5 and [e["kind"] for e in page["items"]] == ["stock_out", "stock_in"]
    assert history(owner_client)["total"] == 6


def test_movements_cannot_be_edited_or_deleted(owner_client):
    banana = new_item(owner_client, opening_quantity="3")
    movement_id = history(owner_client, banana["id"])["items"][0]["id"]
    for method in ("PATCH", "PUT", "DELETE"):
        assert owner_client.request(method, f"{BASE}/movements/{movement_id}", json={}).status_code in (404, 405)
    for statement in ("UPDATE inventory_movements SET quantity_change = 99", "DELETE FROM inventory_movements"):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(text(statement))
    assert history(owner_client, banana["id"])["items"][0]["quantity_change"] == "3"


def test_deleting_an_account_keeps_its_stock_history(owner_client):
    banana = new_item(owner_client, opening_quantity="3")
    employee = employee_client([VIEW, ADJUST], "leaver@example.com")
    move(employee, banana["id"], "stock_out", "1", reason="Smoothies")
    with engine.begin() as conn:  # the retention policy deletes old employee accounts
        conn.execute(text("DELETE FROM accounts WHERE email = 'leaver@example.com'"))
    entries = history(owner_client, banana["id"])["items"]
    assert [(e["kind"], e["actor_name"], e["balance_after"]) for e in entries] == [
        ("stock_out", "Test Employee", "2"), ("opening", "Test Owner", "3")]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM inventory_movements WHERE actor_id IS NULL")).scalar_one() == 1
    # Clearing the actor is the only change allowed; anything alongside it is still refused.
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("UPDATE inventory_movements SET actor_id = NULL, actor_name = 'Someone else' WHERE kind = 'opening'"))


# ---------- concurrency (separate database sessions, released together) ----------


def _run_together(count: int, work) -> list:
    barrier = threading.Barrier(count)
    results: list = [None] * count

    def runner(index: int):
        barrier.wait()
        try:
            results[index] = work(index)
        except ApiError as error:
            results[index] = error.code

    threads = [threading.Thread(target=runner, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def _actor(session) -> Account:
    return session.query(Account).filter_by(email=OWNER_EMAIL).one()


def test_simultaneous_stock_outs_never_oversell(owner_client):
    cups = new_item(owner_client, name="Cups", category="packaging", unit="piece", opening_quantity="5")

    def take_one(_):
        with SessionLocal() as session:
            data = InventoryMovementIn(kind="stock_out", quantity="1", idempotency_key=key())
            return inventory_service.record_movement(session, cups["id"], data, _actor(session))[2]

    results = _run_together(8, take_one)
    assert results.count(True) == 5 and results.count("insufficient_stock") == 3, results
    assert item(owner_client, cups["id"])["quantity"] == "0"
    assert history(owner_client, cups["id"])["total"] == 6


def test_simultaneous_retries_of_one_submission_record_once(owner_client):
    banana = new_item(owner_client, opening_quantity="1")
    same = key()

    def submit(_):
        with SessionLocal() as session:
            data = InventoryMovementIn(kind="stock_in", quantity="2", idempotency_key=same)
            return inventory_service.record_movement(session, banana["id"], data, _actor(session))[2]

    results = _run_together(6, submit)
    assert results.count(True) == 1 and results.count(False) == 5, results
    assert item(owner_client, banana["id"])["quantity"] == "3"


def test_simultaneous_counts_do_not_overwrite_each_other(owner_client):
    banana = new_item(owner_client, opening_quantity="10")

    def count(index):
        with SessionLocal() as session:
            data = InventoryMovementIn(kind="adjustment", quantity=str(index + 1), reason="Count",
                                       version=banana["version"], idempotency_key=key())
            return inventory_service.record_movement(session, banana["id"], data, _actor(session))[2]

    results = _run_together(4, count)
    assert results.count(True) == 1 and results.count("stale_update") == 3, results
    assert history(owner_client, banana["id"])["total"] == 2


# ---------- migration ----------


def _alembic() -> Config:
    here = os.path.dirname(__file__)
    config = Config(os.path.join(here, "..", "alembic.ini"))
    config.set_main_option("script_location", os.path.join(here, "..", "alembic"))
    return config


def test_migration_keeps_existing_records_and_grants_nothing(owner_client, client):
    employee_id = make_account("employee", "existing@example.com", ["bookings.view_all"])
    booking_id = make_booking(client)
    engine.dispose()
    command.downgrade(_alembic(), "0003")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT to_regclass('inventory_items')")).scalar() is None
    finally:
        command.upgrade(_alembic(), "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT permissions FROM accounts WHERE id = :i"), {"i": employee_id}).scalar_one() == ["bookings.view_all"]
        assert conn.execute(text("SELECT count(*) FROM bookings WHERE id = :i"), {"i": booking_id}).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM inventory_items")).scalar_one() == 0
    assert sign_in("existing@example.com").get(f"{BASE}/items").status_code == 403


def test_downgrade_refuses_to_discard_inventory(owner_client):
    new_item(owner_client, opening_quantity="1")
    engine.dispose()
    with pytest.raises(RuntimeError):
        command.downgrade(_alembic(), "0003")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0004"
