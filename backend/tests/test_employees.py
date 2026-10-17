import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Account, ActivityLog

from .conftest import booking_payload, employee_client, make_booking

NEW = {"email": "new.staff@example.com", "full_name": "New Staff"}
NEW_PASSWORD = "a password the employee chose"


def _token(url: str) -> str:
    return re.search(r"token=([\w-]+)", url).group(1)


def test_owner_invites_an_employee_who_sets_their_own_password(owner_client, db):
    created = owner_client.post("/api/owner/employees", json=NEW)

    assert created.status_code == 201
    body = created.json()
    assert body["employee"]["permissions"] == [] and body["employee"]["has_password"] is False  # no access by default
    assert body["setup_url"].startswith("http://localhost:5173/account/reset#token=")  # fragment: never sent to a server
    account = db.scalar(select(Account).where(Account.email == NEW["email"]))
    assert account.role == "employee" and account.password_hash is None

    anyone = TestClient(app)
    assert anyone.post("/api/auth/login", json={"email": NEW["email"], "password": ""}).status_code == 422
    assert anyone.post("/api/auth/login", json={"email": NEW["email"], "password": "anything at all here"}).status_code == 401
    assert anyone.post("/api/auth/password-reset/confirm", json={"token": _token(body["setup_url"]), "new_password": NEW_PASSWORD}).status_code == 204

    signed_in = anyone.post("/api/auth/login", json={"email": NEW["email"], "password": NEW_PASSWORD, "portal": "employee"})
    assert signed_in.status_code == 200 and signed_in.json()["role"] == "employee"
    # The staff sign-in page does not turn them into an owner.
    assert anyone.post("/api/auth/login", json={"email": NEW["email"], "password": NEW_PASSWORD, "portal": "owner"}).status_code == 401
    assert anyone.get("/api/staff/bookings").status_code == 403


def test_invalid_employee_data_is_rejected(owner_client):
    assert owner_client.post("/api/owner/employees", json={**NEW, "permissions": ["everything"]}).status_code == 422
    assert owner_client.post("/api/owner/employees", json={**NEW, "role": "owner"}).status_code == 422
    assert owner_client.post("/api/owner/employees", json={**NEW, "password": "set by owner 123"}).status_code == 422
    assert owner_client.post("/api/owner/employees", json=NEW).status_code == 201
    assert owner_client.post("/api/owner/employees", json=NEW).status_code == 409


def test_permission_changes_apply_on_the_next_request_without_signing_in_again(owner_client, client):
    make_booking(client)
    employee = employee_client([])
    employee_id = owner_client.get("/api/owner/employees").json()[0]["id"]
    assert employee.get("/api/staff/bookings").status_code == 403

    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": ["bookings.view_all"]})
    assert employee.get("/api/staff/bookings").status_code == 200  # same session
    assert employee.get("/api/auth/me").json()["permissions"] == ["bookings.view_all"]

    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": []})
    assert employee.get("/api/staff/bookings").status_code == 403


def test_deactivation_takes_effect_immediately(owner_client):
    employee = employee_client(["bookings.view_all"])
    employee_id = owner_client.get("/api/owner/employees").json()[0]["id"]
    assert employee.get("/api/staff/bookings").status_code == 200

    off = owner_client.patch(f"/api/owner/employees/{employee_id}", json={"is_active": False}).json()
    assert off["is_active"] is False and off["active_sessions"] == 0
    assert employee.get("/api/staff/bookings").status_code == 401
    assert TestClient(app).post("/api/auth/login", json={"email": "employee@example.com", "password": "correct horse battery staple"}).status_code == 401
    assert owner_client.post(f"/api/owner/employees/{employee_id}/setup-link").status_code == 409


def test_owner_can_revoke_sessions_and_issue_a_new_link(owner_client):
    employee = employee_client(["bookings.view_all"])
    employee_id = owner_client.get("/api/owner/employees").json()[0]["id"]
    assert owner_client.get("/api/owner/employees").json()[0]["active_sessions"] == 1

    assert owner_client.post(f"/api/owner/employees/{employee_id}/revoke-sessions").json()["active_sessions"] == 0
    assert employee.get("/api/staff/bookings").status_code == 401

    first = owner_client.post(f"/api/owner/employees/{employee_id}/setup-link").json()["setup_url"]
    second = owner_client.post(f"/api/owner/employees/{employee_id}/setup-link").json()["setup_url"]
    anyone = TestClient(app)
    assert anyone.post("/api/auth/password-reset/confirm", json={"token": _token(first), "new_password": NEW_PASSWORD}).status_code == 400
    assert anyone.post("/api/auth/password-reset/confirm", json={"token": _token(second), "new_password": NEW_PASSWORD}).status_code == 204


def test_employees_cannot_manage_employees_or_their_own_privileges(owner_client):
    employee = employee_client(["bookings.view_all", "menu.manage", "booking_settings.manage"])
    employee_id = owner_client.get("/api/owner/employees").json()[0]["id"]

    assert employee.post("/api/owner/employees", json=NEW).status_code == 403
    assert employee.patch(f"/api/owner/employees/{employee_id}", json={"permissions": ["bookings.cancel"]}).status_code == 403
    assert employee.patch("/api/auth/profile", json={"permissions": ["bookings.cancel"]}).status_code == 422
    assert employee.get("/api/owner/activity").status_code == 403
    assert employee.get("/api/auth/me").json()["permissions"] == ["booking_settings.manage", "bookings.view_all", "menu.manage"]


def test_owner_endpoints_only_manage_employee_accounts(owner_client, customer_client, db):
    customer_id = db.scalar(select(Account.id).where(Account.role == "customer"))
    owner_id = db.scalar(select(Account.id).where(Account.role == "owner"))
    for account_id in (customer_id, owner_id):
        assert owner_client.patch(f"/api/owner/employees/{account_id}", json={"permissions": ["menu.manage"]}).status_code == 404
        assert owner_client.patch(f"/api/owner/employees/{account_id}", json={"is_active": False}).status_code == 404
    assert customer_client.get("/api/auth/me").status_code == 200


def test_activity_log_records_staff_and_owner_actions(owner_client, client, db):
    booking_id = make_booking(client)
    employee = employee_client(["bookings.view_all", "bookings.approve"])
    employee_id = owner_client.get("/api/owner/employees").json()[0]["id"]
    employee.post(f"/api/staff/bookings/{booking_id}/status", json={"status": "confirmed", "version": 1})
    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"permissions": ["bookings.view_all"]})
    owner_client.patch(f"/api/owner/employees/{employee_id}", json={"is_active": False})

    log = owner_client.get("/api/owner/activity").json()
    actions = [(e["action"], e["actor_role"]) for e in reversed(log["items"])]
    assert actions == [("booking.status", "employee"), ("employee.permissions_changed", "owner"), ("employee.deactivated", "owner")]
    assert log["items"][-1]["actor_label"].startswith("Test Employee")
    assert log["items"][1]["detail"] == {"before": ["bookings.approve", "bookings.view_all"], "after": ["bookings.view_all"]}
    by_employee = owner_client.get("/api/owner/activity", params={"actor_id": employee_id}).json()
    assert by_employee["total"] == 1
    assert db.scalar(select(ActivityLog.id).where(ActivityLog.action == "booking.status")) is not None
