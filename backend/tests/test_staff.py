import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, text

from app import booking_service
from app.models import ActivityLog, Booking
from app.permissions import PERMISSIONS
from app.routers.owner import router as owner_router
from app.routers.staff import router as staff_router

from .conftest import booking_payload, employee_client, future_date, make_account, make_booking, sign_in

SETTINGS = {
    "booking_enabled": True,
    "owner_confirmed": True,
    "min_party_size": 2,
    "max_party_size": 4,
    "min_lead_minutes": 60,
    "max_advance_days": 14,
    "slot_interval_minutes": 60,
    "windows": [{"weekday": d, "start_time": "09:00", "end_time": "12:00"} for d in range(7)],
    "overrides": [],
}
ALL = list(PERMISSIONS)


def status(client, booking_id, new, version=None, **extra):
    if version is None:
        version = client.get(f"/api/staff/bookings/{booking_id}").json()["version"]
    return client.post(f"/api/staff/bookings/{booking_id}/status", json={"status": new, "version": version, **extra})


def at(monkeypatch, moment: dt.datetime):
    monkeypatch.setattr(booking_service, "now_local", lambda: moment)


def booking_moment(days=2, hour=10, minute=0):
    return dt.datetime.combine(future_date(days), dt.time(hour, minute), tzinfo=booking_service.get_settings().tz)


# ---------- every staff and owner route needs a signed-in member of staff ----------


def _routes(router):
    return sorted({(m, r.path.replace("{booking_id}", "1").replace("{category_id}", "1").replace("{item_id}", "1")
                    .replace("{employee_id}", "1")) for r in router.routes for m in r.methods - {"HEAD", "OPTIONS"}})


@pytest.mark.parametrize("method,path", _routes(staff_router) + _routes(owner_router))
def test_staff_and_owner_routes_reject_anonymous_and_customers(client, customer_client, method, path):
    assert client.request(method, path, json={}).status_code == 401
    assert customer_client.request(method, path, json={}).status_code == 403


@pytest.mark.parametrize("method,path", _routes(owner_router))
def test_owner_routes_reject_employees_even_with_every_permission(method, path):
    employee = employee_client(ALL)
    assert employee.request(method, path, json={}).status_code == 403


def test_route_inventory_is_as_expected():
    assert len(_routes(staff_router)) == 17 and len(_routes(owner_router)) == 7


# ---------- owner booking management ----------


def test_owner_sees_details_filters_counts_and_history(owner_client, client):
    first = make_booking(client)
    make_booking(client, requested_date=future_date(5).isoformat(), full_name="Later Guest")
    assert status(owner_client, first, "confirmed", reason="Table by the window").status_code == 200

    everything = owner_client.get("/api/staff/bookings").json()
    assert everything["total"] == 2 and everything["scope"] == "all"
    assert everything["counts"]["pending"] == 1 and everything["counts"]["confirmed"] == 1
    detail = owner_client.get(f"/api/staff/bookings/{first}").json()
    assert detail["phone"] == "+9779812345678" and detail["contact_visible"] is True
    assert [(h["from_status"], h["to_status"], h["actor"]) for h in detail["history"]] == [
        (None, "pending", "Guest"), ("pending", "confirmed", "Test Owner")]
    assert detail["history"][1]["reason"] == "Table by the window"

    pending = owner_client.get("/api/staff/bookings", params={"status": "pending"}).json()
    assert [b["full_name"] for b in pending["items"]] == ["Later Guest"]
    day = future_date().isoformat()
    assert [b["id"] for b in owner_client.get("/api/staff/bookings", params={"date_from": day, "date_to": day}).json()["items"]] == [first]
    assert owner_client.get("/api/staff/bookings", params={"status": "bogus"}).status_code == 422


def test_full_status_flow_with_time_rules(owner_client, client, monkeypatch, db):
    booking_id = make_booking(client)  # two days ahead, 10:00

    assert status(owner_client, booking_id, "checked_in").status_code == 409  # not confirmed yet
    assert status(owner_client, booking_id, "confirmed").status_code == 200
    early = status(owner_client, booking_id, "checked_in")
    assert early.status_code == 409 and early.json()["error"]["code"] == "not_allowed_now"  # wrong day
    assert status(owner_client, booking_id, "no_show").status_code == 409  # time has not passed
    assert status(owner_client, booking_id, "completed").status_code == 409  # must check in first

    at(monkeypatch, booking_moment(hour=9, minute=50))  # the day itself, in Pokhara
    assert owner_client.get(f"/api/staff/bookings/{booking_id}").json()["allowed_statuses"] == ["checked_in", "cancelled"]
    assert status(owner_client, booking_id, "checked_in").status_code == 200
    assert status(owner_client, booking_id, "cancelled").status_code == 409
    assert status(owner_client, booking_id, "completed").status_code == 200
    for terminal_attempt in ("confirmed", "cancelled", "checked_in"):
        assert status(owner_client, booking_id, terminal_attempt).status_code == 409
    assert db.get(Booking, booking_id).status == "completed"


def test_no_show_only_after_the_time_and_past_requests_cannot_be_confirmed(owner_client, client, monkeypatch):
    confirmed, still_pending = make_booking(client), make_booking(client, requested_time="11:00")
    status(owner_client, confirmed, "confirmed")

    at(monkeypatch, booking_moment(hour=12))
    assert status(owner_client, confirmed, "no_show").status_code == 200
    late = status(owner_client, still_pending, "confirmed")
    assert late.status_code == 409 and "already passed" in late.json()["error"]["message"]
    assert status(owner_client, still_pending, "declined").status_code == 200


def test_stale_version_is_a_conflict_not_an_overwrite(owner_client, client, db):
    booking_id = make_booking(client)
    seen = owner_client.get(f"/api/staff/bookings/{booking_id}").json()["version"]
    owner_client.patch(f"/api/staff/bookings/{booking_id}", json={"internal_notes": "Called the guest", "version": seen})

    stale = status(owner_client, booking_id, "declined", version=seen)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_update"
    assert db.get(Booking, booking_id).status == "pending"
    stale_notes = owner_client.patch(f"/api/staff/bookings/{booking_id}", json={"internal_notes": "overwrite", "version": seen})
    assert stale_notes.status_code == 409
    assert db.get(Booking, booking_id).internal_notes == "Called the guest"
    assert owner_client.post(f"/api/staff/bookings/{booking_id}/status", json={"status": "confirmed"}).status_code == 422  # version required


def test_simultaneous_staff_actions_cannot_both_win(client, db):
    make_account("owner", "owner@example.com")
    booking_id = make_booking(client)
    clients = [sign_in("owner@example.com") for _ in range(2)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: status(pair[0], booking_id, pair[1], version=1),
                                zip(clients, ("confirmed", "declined"))))

    assert sorted(r.status_code for r in results) == [200, 409]
    winner = next(r for r in results if r.status_code == 200).json()["status"]
    assert db.get(Booking, booking_id).status == winner
    assert db.execute(text("SELECT count(*) FROM booking_status_history WHERE booking_id = :b"), {"b": booking_id}).scalar() == 2


def test_notes_endpoint_cannot_change_status_and_actions_are_logged(owner_client, client, db):
    booking_id = make_booking(client)
    assert owner_client.patch(f"/api/staff/bookings/{booking_id}", json={"status": "confirmed", "version": 1}).status_code == 422
    status(owner_client, booking_id, "confirmed")
    logged = db.scalars(select(ActivityLog).order_by(ActivityLog.id)).all()
    assert [(e.action, e.actor_role) for e in logged] == [("booking.status", "owner")]
    assert logged[0].detail["to_status"] == "confirmed"
    # Guest contact details are not copied into the activity log.
    assert "9812345678" not in str([e.detail for e in logged])


# ---------- employee permissions ----------


def test_employee_without_permissions_can_do_nothing(client):
    booking_id = make_booking(client)
    employee = employee_client([])
    assert employee.get("/api/auth/me").json() | {"csrf_token": ""} == {
        "id": 1, "email": "employee@example.com", "full_name": "Test Employee", "phone": None, "role": "employee",
        "permissions": [], "csrf_token": ""}
    for path in ("/api/staff/bookings", "/api/staff/alerts", "/api/staff/menu", "/api/staff/settings"):
        assert employee.get(path).status_code == 403
    assert employee.get(f"/api/staff/bookings/{booking_id}").status_code == 404
    assert employee.post(f"/api/staff/bookings/{booking_id}/status", json={"status": "confirmed", "version": 1}).status_code == 404


def test_contact_details_are_left_out_of_every_response_without_permission(client):
    booking_id = make_booking(client)
    hidden = employee_client(["bookings.view_all", "bookings.approve", "bookings.edit_notes"])

    responses = [
        hidden.get("/api/staff/bookings"),
        hidden.get(f"/api/staff/bookings/{booking_id}"),
        hidden.patch(f"/api/staff/bookings/{booking_id}", json={"internal_notes": "n", "version": 1}),
        hidden.post(f"/api/staff/bookings/{booking_id}/status", json={"status": "confirmed", "version": 2}),
    ]
    for response in responses:
        assert response.status_code == 200
        assert "9812345678" not in response.text and "guest@example.com" not in response.text
    detail = responses[1].json()
    assert detail["phone"] is None and detail["email"] is None and detail["contact_visible"] is False

    allowed = employee_client(["bookings.view_all", "bookings.view_contact"], "contact@example.com")
    assert allowed.get(f"/api/staff/bookings/{booking_id}").json()["phone"] == "+9779812345678"


@pytest.mark.parametrize("permission,target,prepare", [
    ("bookings.approve", "confirmed", None),
    ("bookings.decline", "declined", None),
    ("bookings.cancel", "cancelled", None),
    ("bookings.check_in", "checked_in", "confirmed"),
    ("bookings.mark_no_show", "no_show", "confirmed"),
    ("bookings.complete", "completed", "checked_in"),
])
def test_each_action_needs_its_own_permission(owner_client, client, monkeypatch, permission, target, prepare):
    booking_id = make_booking(client)
    if prepare:
        status(owner_client, booking_id, "confirmed")
    at(monkeypatch, booking_moment(hour=9, minute=59) if target != "no_show" else booking_moment(hour=12))
    if prepare == "checked_in":
        status(owner_client, booking_id, "checked_in")

    without = employee_client([p for p in ALL if p != permission], "without@example.com")
    refused = status(without, booking_id, target)
    assert refused.status_code == 403, refused.text
    assert target not in without.get(f"/api/staff/bookings/{booking_id}").json()["allowed_statuses"]

    only = employee_client(["bookings.view_all", permission], "only@example.com")
    assert status(only, booking_id, target).status_code == 200


def test_view_assigned_limits_the_scope(owner_client, client):
    mine, other = make_booking(client), make_booking(client, requested_time="11:00")
    employee = employee_client(["bookings.view_assigned", "bookings.approve"])
    employee_id = owner_client.get("/api/staff/assignable").json()[0]["id"]

    assert employee.get("/api/staff/bookings").json()["total"] == 0
    assigned = owner_client.post(f"/api/staff/bookings/{mine}/assign", json={"employee_id": employee_id, "version": 1})
    assert assigned.json()["assigned_employee"]["full_name"] == "Test Employee"

    listed = employee.get("/api/staff/bookings").json()
    assert [b["id"] for b in listed["items"]] == [mine] and listed["scope"] == "assigned"
    assert employee.get("/api/staff/alerts").json()["pending_count"] == 1
    assert employee.get(f"/api/staff/bookings/{other}").status_code == 404
    assert status(employee, other, "confirmed", version=1).status_code == 404
    assert status(employee, mine, "confirmed").status_code == 200
    # Employees cannot assign bookings, even their own.
    assert employee.post(f"/api/staff/bookings/{mine}/assign", json={"employee_id": None, "version": 3}).status_code == 403
    # Reassigning away removes access at once.
    owner_client.post(f"/api/staff/bookings/{mine}/assign", json={"employee_id": None, "version": 3})
    assert employee.get(f"/api/staff/bookings/{mine}").status_code == 404


def test_notes_and_cancellation_resolution_need_permission(client, customer_client):
    booking_id = make_booking(customer_client, "/api/customer/bookings")
    ref = customer_client.get("/api/customer/bookings").json()["items"][0]["reference"]
    customer_client.post(f"/api/customer/bookings/{ref}/cancellation-request", json={})
    viewer = employee_client(["bookings.view_all"])

    assert viewer.patch(f"/api/staff/bookings/{booking_id}", json={"internal_notes": "x", "version": 2}).status_code == 403
    assert viewer.post(f"/api/staff/bookings/{booking_id}/cancellation", json={"decision": "approve", "version": 2}).status_code == 403
    detail = viewer.get(f"/api/staff/bookings/{booking_id}").json()
    assert detail["can_edit_notes"] is False and detail["can_resolve_cancellation"] is False


# ---------- settings ----------


def test_owner_configured_limits_apply_to_new_requests(owner_client, client):
    assert owner_client.get("/api/staff/settings").json()["owner_confirmed"] is False
    closed = future_date(4).isoformat()
    saved = owner_client.put("/api/staff/settings", json={**SETTINGS, "overrides": [{"date": closed, "is_closed": True, "note": "Festival"}]})
    assert saved.status_code == 200 and saved.json()["overrides"][0]["note"] == "Festival"

    config = client.get("/api/booking/config").json()
    assert (config["min_party_size"], config["max_party_size"]) == (2, 4)
    assert client.post("/api/bookings", json=booking_payload(party_size=5)).status_code == 422
    assert client.post("/api/bookings", json=booking_payload(requested_time="13:00")).status_code == 422
    assert client.post("/api/bookings", json=booking_payload(party_size=3, requested_date=closed, requested_time="10:00")).status_code == 422
    assert client.post("/api/bookings", json=booking_payload(party_size=4, requested_time="11:00")).status_code == 201


@pytest.mark.parametrize("change", [
    {"min_party_size": 6, "max_party_size": 2},
    {"slot_interval_minutes": 7},
    {"windows": [{"weekday": 0, "start_time": "12:00", "end_time": "09:00"}]},
    {"windows": [{"weekday": 0, "start_time": "09:00", "end_time": "12:00"}, {"weekday": 0, "start_time": "11:00", "end_time": "14:00"}]},
    {"overrides": [{"date": "2030-01-01", "is_closed": False}]},
    {"overrides": [{"date": "2030-01-01", "is_closed": True}, {"date": "2030-01-01", "is_closed": True}]},
])
def test_invalid_settings_are_rejected(owner_client, change):
    assert owner_client.put("/api/staff/settings", json={**SETTINGS, **change}).status_code == 422
    assert owner_client.get("/api/staff/settings").json()["max_party_size"] == 8


def test_settings_permission_and_owner_only_confirmation(owner_client):
    assert employee_client(["bookings.view_all"], "viewer@example.com").put("/api/staff/settings", json=SETTINGS).status_code == 403
    manager = employee_client(["booking_settings.manage"])
    # May change the rules, but not confirm them for real use.
    assert manager.put("/api/staff/settings", json=SETTINGS).status_code == 403
    assert manager.put("/api/staff/settings", json={**SETTINGS, "owner_confirmed": False}).status_code == 200
    assert owner_client.put("/api/staff/settings", json=SETTINGS).json()["owner_confirmed"] is True
