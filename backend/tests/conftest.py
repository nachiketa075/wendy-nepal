"""Tests run against a real PostgreSQL database given by TEST_DATABASE_URL.

The schema is dropped and rebuilt through the Alembic migrations, so the
database name must end in "_test" to avoid ever pointing at real data.
"""

import datetime as dt
import os

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.exit("Set TEST_DATABASE_URL to a PostgreSQL database whose name ends in _test.", returncode=2)
if not TEST_DATABASE_URL.split("?")[0].endswith("_test"):
    pytest.exit("Refusing to run: TEST_DATABASE_URL database name must end in _test.", returncode=2)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["EMAIL_DELIVERY"] = "memory"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.booking_service import now_local  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app import email_delivery  # noqa: E402
from app.models import Account  # noqa: E402
from app.rate_limit import limiter  # noqa: E402
from app.security import hash_password  # noqa: E402

OWNER_EMAIL = "owner@example.com"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(config, "head")
    yield
    engine.dispose()


PASSWORD = "correct horse battery staple"
OWNER_PASSWORD = PASSWORD


@pytest.fixture(autouse=True)
def clean_state():
    limiter.reset()
    email_delivery.TEST_OUTBOX.clear()
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE bookings, booking_status_history, accounts, account_sessions, password_reset_tokens, "
            "activity_log, booking_date_overrides RESTART IDENTITY CASCADE"
        ))
        conn.execute(text("DELETE FROM menu_items WHERE source IN ('owner', 'owner_pdf')"))
        conn.execute(text("DELETE FROM menu_categories WHERE slug NOT IN ('drinks', 'bowls', 'bites')"))
        conn.execute(text("UPDATE menu_items SET is_published = true, is_available = true"))
        conn.execute(
            text(
                "UPDATE booking_settings SET booking_enabled = true, owner_confirmed = false, "
                "min_party_size = 1, max_party_size = 8, min_lead_minutes = 120, "
                "max_advance_days = 30, slot_interval_minutes = 30"
            )
        )
        conn.execute(text("DELETE FROM booking_windows"))
        conn.execute(
            text(
                "INSERT INTO booking_windows (weekday, start_time, end_time) "
                "SELECT d, '08:00', '18:00' FROM generate_series(0, 6) AS d"
            )
        )
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_account(role: str, email: str, permissions: list[str] | None = None, name: str | None = None,
                 password: str | None = PASSWORD) -> int:
    with SessionLocal() as session:
        account = Account(email=email, role=role, full_name=name or f"Test {role.title()}",
                          password_hash=hash_password(password) if password else None, permissions=permissions or [])
        session.add(account)
        session.commit()
        return account.id


def sign_in(email: str, password: str = PASSWORD) -> TestClient:
    """A client signed in as this account, sending the CSRF header automatically."""
    c = TestClient(app)
    response = c.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    c.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return c


@pytest.fixture
def owner_client():
    make_account("owner", OWNER_EMAIL)
    return sign_in(OWNER_EMAIL)


@pytest.fixture
def customer_client():
    make_account("customer", "customer.a@example.com", name="Customer A")
    return sign_in("customer.a@example.com")


def employee_client(permissions: list[str], email: str = "employee@example.com") -> TestClient:
    make_account("employee", email, permissions)
    return sign_in(email)


def future_date(days: int = 2) -> dt.date:
    return now_local().date() + dt.timedelta(days=days)


def booking_payload(**overrides) -> dict:
    payload = {
        "full_name": "Test Guest",
        "phone": "+977 9812345678",
        "email": "guest@example.com",
        "requested_date": future_date().isoformat(),
        "requested_time": "10:00",
        "party_size": 2,
        "special_requests": "Window seat if possible",
    }
    payload.update(overrides)
    return payload


def booking_id_for(reference: str) -> int:
    with engine.begin() as conn:
        return conn.execute(text("SELECT id FROM bookings WHERE reference = :r"), {"r": reference}).scalar_one()


def make_booking(client: TestClient, path: str = "/api/bookings", **overrides) -> int:
    response = client.post(path, json=booking_payload(**overrides))
    assert response.status_code in (200, 201), response.text
    return booking_id_for(response.json()["reference"])
