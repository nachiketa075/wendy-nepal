"""Changing your own password while signed in (POST /api/auth/password)."""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.main import app
from app.models import Account, PasswordResetToken
from app.security import verify_password

from .conftest import OWNER_EMAIL, PASSWORD, employee_client, make_account, sign_in

NEW = "Mango-lassi-by-the-lake-2026"


def body(current=PASSWORD, new=NEW, confirm=None):
    return {"current_password": current, "new_password": new, "confirm_new_password": new if confirm is None else confirm}


def hash_of(db, email):
    db.expire_all()
    return db.scalar(select(Account.password_hash).where(Account.email == email))


def login(email, password):
    return TestClient(app).post("/api/auth/login", json={"email": email, "password": password}).status_code


@pytest.fixture
def customer():
    make_account("customer", "c@example.com")
    return sign_in("c@example.com")


def test_correct_current_password_changes_it_and_the_new_one_is_hashed(customer, db):
    before = hash_of(db, "c@example.com")
    response = customer.post("/api/auth/password", json=body())
    assert response.status_code == 204 and response.content == b""  # nothing returned, certainly no hash
    after = hash_of(db, "c@example.com")
    assert after != before and after.startswith("$argon2id$") and NEW not in after
    assert verify_password(NEW, after) and not verify_password(PASSWORD, after)
    assert login("c@example.com", PASSWORD) == 401
    assert login("c@example.com", NEW) == 200
    assert "password" not in customer.get("/api/auth/me").text.lower().replace("password_reset", "")


def test_wrong_current_password_is_refused_and_nothing_changes(customer, db):
    before = hash_of(db, "c@example.com")
    response = customer.post("/api/auth/password", json=body(current="not my password at all"))
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {"current_password": "That is not your current password."}
    assert hash_of(db, "c@example.com") == before and login("c@example.com", PASSWORD) == 200


@pytest.mark.parametrize("payload,expected", [
    (body(current="", new="", confirm=""), {
        "current_password": "Enter your current password.",
        "new_password": "Enter a new password.",
        "confirm_new_password": "Enter the new password again.",
    }),
    (body(confirm="Mango-lassi-by-the-lake-2027"), {"confirm_new_password": "The new passwords do not match."}),
    (body(new="too short", confirm="too short"), {"new_password": "Use at least 12 characters."}),
    (body(new="x" * 257, confirm="x" * 257), {"new_password": "String should have at most 256 characters"}),
])
def test_form_problems_are_reported_per_field_and_change_nothing(customer, db, payload, expected):
    before = hash_of(db, "c@example.com")
    response = customer.post("/api/auth/password", json=payload)
    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    for name, message in expected.items():
        assert fields[name] == message
    assert hash_of(db, "c@example.com") == before
    for secret in (payload["current_password"], payload["new_password"]):
        if secret:
            assert secret not in response.text  # passwords are never echoed back


def test_confirmation_is_required_by_the_server(customer):
    response = customer.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW})
    assert response.status_code == 422 and "confirm_new_password" in response.json()["error"]["fields"]


def test_new_password_must_differ_from_the_current_one(customer, db):
    before = hash_of(db, "c@example.com")
    response = customer.post("/api/auth/password", json=body(new=PASSWORD))
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {"new_password": "Choose a password different from your current one."}
    assert hash_of(db, "c@example.com") == before


def test_signed_out_expired_or_forged_requests_are_refused(customer, db):
    assert TestClient(app).post("/api/auth/password", json=body()).status_code == 401
    db.execute(text("UPDATE account_sessions SET expires_at = now() - interval '1 second'"))
    db.commit()
    assert customer.post("/api/auth/password", json=body()).json()["error"]["code"] == "not_authenticated"

    fresh = sign_in("c@example.com")
    fresh.headers.pop("X-CSRF-Token")
    assert fresh.post("/api/auth/password", json=body()).json()["error"]["code"] == "csrf_failed"
    assert fresh.post("/api/auth/password", json=body(), headers={"Origin": "https://evil.example"}).status_code == 403
    assert login("c@example.com", PASSWORD) == 200  # unchanged throughout


def test_other_sessions_end_and_this_one_continues(customer):
    elsewhere = sign_in("c@example.com")
    assert customer.post("/api/auth/password", json=body()).status_code == 204
    assert customer.get("/api/auth/me").status_code == 200
    assert elsewhere.get("/api/auth/me").status_code == 401


def test_unused_reset_and_setup_links_stop_working(customer, db, client):
    client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    assert db.scalar(select(PasswordResetToken).where(PasswordResetToken.used_at.is_(None))) is not None
    assert customer.post("/api/auth/password", json=body()).status_code == 204
    db.expire_all()
    assert db.scalar(select(PasswordResetToken).where(PasswordResetToken.used_at.is_(None))) is None


def test_wrong_current_password_attempts_are_rate_limited(customer):
    for _ in range(5):
        assert customer.post("/api/auth/password", json=body(current="guessing the password")).status_code == 422
    limited = customer.post("/api/auth/password", json=body())
    assert limited.status_code == 429 and limited.headers["Retry-After"]
    assert login("c@example.com", PASSWORD) == 200


def test_owner_and_employee_change_their_own_password_and_keep_their_access(owner_client, db):
    employee = employee_client(["bookings.view_all", "inventory.view"], "staff@example.com")
    for client_, email in ((owner_client, OWNER_EMAIL), (employee, "staff@example.com")):
        assert client_.post("/api/auth/password", json=body()).status_code == 204
        assert login(email, NEW) == 200
    me = employee.get("/api/auth/me").json()
    assert me["role"] == "employee" and me["permissions"] == ["bookings.view_all", "inventory.view"]
    assert employee.get("/api/staff/bookings").status_code == 200 and employee.get("/api/staff/menu").status_code == 403
    assert owner_client.get("/api/owner/employees").status_code == 200
    log = owner_client.get("/api/owner/activity").json()["items"]
    assert [e["action"] for e in log[:2]] == ["account.password_changed", "account.password_changed"]


def test_passwords_never_reach_the_logs(customer, caplog):
    caplog.set_level(logging.DEBUG)
    customer.post("/api/auth/password", json=body(current="a wrong guess, logged?"))
    customer.post("/api/auth/password", json=body(confirm="mismatching confirmation"))
    customer.post("/api/auth/password", json=body())
    for secret in (PASSWORD, NEW, "a wrong guess, logged?", "mismatching confirmation"):
        assert secret not in caplog.text
