import datetime as dt
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import email_delivery
from app.config import Settings
from app.main import app
from app.models import Account, AccountSession, PasswordResetToken

from .conftest import OWNER_EMAIL, PASSWORD, make_account, sign_in

REGISTER = {"full_name": "New Customer", "email": "new.customer@example.com", "password": "a long enough password"}


# ---------- registration ----------


def test_registration_creates_a_customer_and_signs_them_in(client, db):
    response = client.post("/api/auth/register", json={**REGISTER, "phone": "+977 9812345678"})

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "customer" and body["permissions"] == [] and body["phone"] == "+9779812345678"
    account = db.scalar(select(Account))
    assert account.role == "customer" and account.password_hash.startswith("$argon2id$")
    assert client.get("/api/auth/me").json()["email"] == "new.customer@example.com"


@pytest.mark.parametrize("extra", [{"role": "owner"}, {"role": "employee"}, {"permissions": ["bookings.view_all"]},
                                   {"is_active": True}, {"id": 1}])
def test_registration_rejects_privileged_fields(client, db, extra):
    response = client.post("/api/auth/register", json={**REGISTER, **extra})

    assert response.status_code == 422
    assert db.scalar(select(Account)) is None


@pytest.mark.parametrize("change,field", [({"password": "short"}, "password"), ({"email": "nope"}, "email"),
                                          ({"full_name": " "}, "full_name"), ({"phone": "12345"}, "phone")])
def test_registration_validation(client, change, field):
    response = client.post("/api/auth/register", json={**REGISTER, **change})
    assert response.status_code == 422 and field in response.json()["error"]["fields"]


def test_duplicate_email_is_refused_case_insensitively(client):
    assert client.post("/api/auth/register", json=REGISTER).status_code == 201
    again = TestClient(app).post("/api/auth/register", json={**REGISTER, "email": "NEW.Customer@Example.com"})
    assert again.status_code == 409


def test_there_is_no_public_owner_or_employee_registration(client):
    for path in ("/api/owner/register", "/api/employee/register", "/api/staff/register", "/api/auth/register-owner"):
        assert client.post(path, json=REGISTER).status_code in (401, 404, 405)
    # Creating an employee needs an owner session.
    assert client.post("/api/owner/employees", json={"email": "e@example.com", "full_name": "E E"}).status_code == 401


# ---------- sign-in, sessions ----------


def test_login_sets_a_hardened_cookie_and_stores_only_a_digest(db):
    make_account("owner", OWNER_EMAIL)
    with TestClient(app) as c:
        response = c.post("/api/auth/login", json={"email": OWNER_EMAIL.upper(), "password": PASSWORD})
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
        token = c.cookies.get("wendy_session")
    assert response.json()["role"] == "owner"
    assert token not in {s.token_hash for s in db.scalars(select(AccountSession))}


def test_secure_cookie_in_production():
    production = dict(environment="production", database_url="postgresql+psycopg://u:p@h/d",
                      cors_origins="https://wendy.example", public_site_url="https://wendy.example", email_delivery="disabled")
    assert Settings(**production).secure_cookies is True
    for unsafe in ({"cors_origins": "*"}, {"cors_origins": "http://wendy.example"}, {"cookie_secure": False},
                   {"public_site_url": "http://wendy.example"}, {"email_delivery": "smtp"}):
        with pytest.raises(ValueError):
            Settings(**{**production, **unsafe})
    with pytest.raises(ValueError):
        Settings(environment="production", database_url="x", cors_origins="https://wendy.example",
                 public_site_url="https://wendy.example", email_delivery="dev_file")
    with pytest.raises(ValueError):
        Settings(environment="development", database_url="x", email_delivery="memory")


def test_wrong_password_and_unknown_email_get_the_same_answer(client):
    make_account("customer", "known@example.com")
    wrong = client.post("/api/auth/login", json={"email": "known@example.com", "password": "wrong password here"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers


def test_the_sign_in_page_never_decides_the_role(client):
    """A customer using the owner or staff page gets no session, and a role sent by the client is rejected."""
    make_account("customer", "customer@example.com")
    for portal in ("owner", "employee"):
        refused = client.post("/api/auth/login", json={"email": "customer@example.com", "password": PASSWORD, "portal": portal})
        assert refused.status_code == 401 and "set-cookie" not in refused.headers
    assert client.post("/api/auth/login", json={"email": "customer@example.com", "password": PASSWORD, "role": "owner"}).status_code == 422

    signed_in = sign_in("customer@example.com")
    assert signed_in.get("/api/auth/me").json()["role"] == "customer"
    for path in ("/api/staff/bookings", "/api/staff/menu", "/api/staff/settings", "/api/owner/employees", "/api/owner/activity"):
        assert signed_in.get(path).status_code == 403


def test_login_is_rate_limited(client):
    make_account("owner", OWNER_EMAIL)
    attempt = {"email": OWNER_EMAIL, "password": "wrong password here"}
    statuses = [client.post("/api/auth/login", json=attempt).status_code for _ in range(6)]
    assert statuses == [401] * 5 + [429]
    assert client.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD}).status_code == 429


def test_logout_expiry_and_forged_cookies(db):
    make_account("customer", "c@example.com")
    c = sign_in("c@example.com")
    assert c.get("/api/auth/me").status_code == 200

    session = db.scalar(select(AccountSession))
    session.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    db.commit()
    assert c.get("/api/auth/me").status_code == 401  # expired

    c = sign_in("c@example.com")
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401  # logged out

    forged = TestClient(app)
    forged.cookies.set("wendy_session", "not-a-real-token")
    assert forged.get("/api/auth/me").status_code == 401


def test_csrf_token_and_origin_are_required_for_changes():
    make_account("customer", "c@example.com")
    c = sign_in("c@example.com")
    token = c.headers.pop("X-CSRF-Token")
    assert c.patch("/api/auth/profile", json={"full_name": "Changed"}).status_code == 403
    c.headers["X-CSRF-Token"] = "wrong"
    assert c.patch("/api/auth/profile", json={"full_name": "Changed"}).json()["error"]["code"] == "csrf_failed"
    c.headers["X-CSRF-Token"] = token
    evil = c.patch("/api/auth/profile", json={"full_name": "Changed"}, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403 and evil.json()["error"]["code"] == "bad_origin"
    assert c.get("/api/auth/me").json()["full_name"] == "Test Customer"


# ---------- profile and password ----------


def test_profile_update_cannot_change_email_role_or_permissions(db):
    make_account("customer", "c@example.com")
    c = sign_in("c@example.com")
    updated = c.patch("/api/auth/profile", json={"full_name": "Renamed Person", "phone": "+91 98765 43210"}).json()
    assert updated["full_name"] == "Renamed Person" and updated["phone"] == "+919876543210"
    for sneaky in ({"role": "owner"}, {"permissions": ["menu.manage"]}, {"email": "x@example.com"}, {"is_active": False}):
        assert c.patch("/api/auth/profile", json=sneaky).status_code == 422
    assert db.scalar(select(Account)).role == "customer"


def test_password_change_needs_the_current_password_and_signs_out_other_devices():
    make_account("customer", "c@example.com")
    here, elsewhere = sign_in("c@example.com"), sign_in("c@example.com")
    new = "a brand new long password"

    assert here.post("/api/auth/password", json={"current_password": "wrong one entirely", "new_password": new}).status_code == 422
    assert here.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "short"}).status_code == 422
    assert here.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": new}).status_code == 204

    assert here.get("/api/auth/me").status_code == 200
    assert elsewhere.get("/api/auth/me").status_code == 401
    assert TestClient(app).post("/api/auth/login", json={"email": "c@example.com", "password": PASSWORD}).status_code == 401
    assert TestClient(app).post("/api/auth/login", json={"email": "c@example.com", "password": new}).status_code == 200


# ---------- password reset ----------


def _token_from_outbox() -> str:
    assert len(email_delivery.TEST_OUTBOX) == 1
    return re.search(r"token=([\w-]+)", email_delivery.TEST_OUTBOX[0]["body"]).group(1)


def test_reset_request_answers_the_same_for_known_and_unknown_emails(client, db):
    make_account("customer", "c@example.com")
    known = client.post("/api/auth/password-reset/request", json={"email": "C@example.com"})
    unknown = client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(email_delivery.TEST_OUTBOX) == 1  # only the real account got a message
    stored = db.scalar(select(PasswordResetToken))
    assert stored.token_hash != _token_from_outbox() and len(stored.token_hash) == 64  # hash only


def test_reset_token_is_single_use_short_lived_and_signs_everyone_out(client, db):
    make_account("customer", "c@example.com")
    signed_in = sign_in("c@example.com")
    client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    token, new = _token_from_outbox(), "a freshly chosen password"

    assert client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": "short"}).status_code == 422
    assert client.post("/api/auth/password-reset/confirm", json={"token": "x" * 43, "new_password": new}).status_code == 400
    assert client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": new}).status_code == 204
    assert client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": new}).status_code == 400  # used

    assert signed_in.get("/api/auth/me").status_code == 401
    assert TestClient(app).post("/api/auth/login", json={"email": "c@example.com", "password": new}).status_code == 200


def test_expired_reset_token_is_refused(client, db):
    make_account("customer", "c@example.com")
    client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    db.execute(text("UPDATE password_reset_tokens SET expires_at = now() - interval '1 second'"))
    db.commit()
    response = client.post("/api/auth/password-reset/confirm", json={"token": _token_from_outbox(), "new_password": "a freshly chosen password"})
    assert response.status_code == 400 and response.json()["error"]["code"] == "invalid_token"


def test_a_new_reset_request_cancels_the_previous_link(client):
    make_account("customer", "c@example.com")
    client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    first = _token_from_outbox()
    email_delivery.TEST_OUTBOX.clear()
    client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    assert client.post("/api/auth/password-reset/confirm", json={"token": first, "new_password": "a freshly chosen password"}).status_code == 400


def test_without_email_delivery_nothing_is_claimed_or_created(client, db, monkeypatch):
    make_account("customer", "c@example.com")
    monkeypatch.setattr(email_delivery.get_settings(), "email_delivery", "disabled")

    assert client.get("/api/auth/config").json()["password_reset_by_email"] is False
    response = client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    assert response.json()["email_delivery"] is False and "not set up" in response.json()["message"]
    assert db.scalar(select(PasswordResetToken)) is None and email_delivery.TEST_OUTBOX == []


def test_dev_file_delivery_writes_to_a_folder_not_the_log(client, tmp_path, monkeypatch, caplog):
    make_account("customer", "c@example.com")
    settings = email_delivery.get_settings()
    monkeypatch.setattr(settings, "email_delivery", "dev_file")
    monkeypatch.setattr(settings, "dev_mailbox_dir", str(tmp_path))
    with caplog.at_level("INFO"):
        client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    files = list(tmp_path.iterdir())
    assert len(files) == 1 and "token=" in files[0].read_text()
    assert "token=" not in caplog.text and "c@example.com" not in caplog.text


def test_reset_link_keeps_the_token_out_of_server_logs(client):
    """The token is in the URL fragment, which browsers do not send to servers."""
    make_account("customer", "c@example.com")
    client.post("/api/auth/password-reset/request", json={"email": "c@example.com"})
    link = re.search(r"https?://\S+", email_delivery.TEST_OUTBOX[0]["body"]).group(0)
    assert "/account/reset#token=" in link and "?" not in link


def test_one_stranger_cannot_lock_an_account_for_everyone(client):
    make_account("owner", OWNER_EMAIL)
    attempt = {"email": OWNER_EMAIL, "password": "wrong password here"}
    assert [client.post("/api/auth/login", json=attempt).status_code for _ in range(6)][-1] == 429

    # The real owner, arriving from another address, can still sign in.
    from app import rate_limit
    from app.routers import auth as auth_router

    original = auth_router.client_ip
    auth_router.client_ip = lambda request: "203.0.113.9"
    try:
        assert client.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD}).status_code == 200
    finally:
        auth_router.client_ip = original
    assert rate_limit.limiter is not None


def test_readiness_and_cache_headers(client, db):
    assert client.get("/api/health").json() == {"status": "ok"}
    ready = client.get("/api/ready")
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}

    db.execute(text("UPDATE alembic_version SET version_num = '0002'"))
    db.commit()
    try:
        pending = client.get("/api/ready")
        assert pending.status_code == 503 and pending.json() == {"status": "migration_pending"}
        assert "postgres" not in pending.text.lower()
    finally:
        db.execute(text("UPDATE alembic_version SET version_num = '0003'"))
        db.commit()

    make_account("customer", "c@example.com")
    signed_in = sign_in("c@example.com")
    assert signed_in.get("/api/auth/me").headers["cache-control"] == "no-store"
    assert signed_in.get("/api/customer/bookings").headers["cache-control"] == "no-store"
    assert client.get("/api/menu").headers["cache-control"] == "public, max-age=60"
    assert client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope nope nope"}).headers["cache-control"] == "no-store"
