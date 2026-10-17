"""F-01 regression: unexpected errors must not put customer data in the logs."""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app import booking_service
from app.database import engine
from app.main import app
from app.safe_logging import describe_exception

from .conftest import booking_payload, make_account

# Synthetic values that would be recognisable anywhere in a log.
NAME = "Zephyrine Quillfeather"
PHONE_DIGITS = "9811122233"
EMAIL = "zephyrine.quillfeather@example.com"
NOTE = "Allergic to walnuts-SENTINEL-7731"
SENSITIVE = (NAME, "Zephyrine", "Quillfeather", PHONE_DIGITS, EMAIL, "SENTINEL-7731")


def _assert_clean(log_text: str) -> None:
    for value in SENSITIVE:
        assert value not in log_text, f"log contains {value!r}"
    assert "[parameters:" not in log_text and "[SQL:" not in log_text


@pytest.fixture
def all_logs(caplog):
    """Capture every logger at DEBUG, including SQLAlchemy and server loggers."""
    caplog.set_level(logging.DEBUG)
    for name in ("sqlalchemy", "sqlalchemy.engine", "uvicorn", "uvicorn.error", "uvicorn.access", "wendy"):
        caplog.set_level(logging.DEBUG, logger=name)
    return caplog


def test_engine_hides_statement_parameters():
    assert engine.hide_parameters is True


def test_unexpected_database_error_is_logged_without_customer_data(all_logs, monkeypatch):
    # A reference longer than its column makes the INSERT fail with a database
    # error the booking code does not anticipate. The INSERT's parameters are
    # the guest's name, phone, email and notes.
    monkeypatch.setattr(booking_service, "_new_reference", lambda: "WJ-" + "X" * 40)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/bookings", json=booking_payload(
        full_name=NAME, phone=f"+977 {PHONE_DIGITS}", email=EMAIL, special_requests=NOTE))

    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "server_error" and len(body["reference"]) == 12
    assert response.headers["cache-control"] == "no-store"
    _assert_clean(response.text)

    log_text = all_logs.text
    _assert_clean(log_text)
    # ...while keeping what is needed to diagnose it.
    line = next(r.getMessage() for r in all_logs.records if r.name == "wendy.errors")
    assert f"id={body['reference']}" in line
    assert "POST /api/bookings" in line
    assert "sqlalchemy.exc.DataError" in line and "sqlstate=22001" in line
    assert "booking_service.py" in line and "create_booking" in line


def test_database_detail_with_row_values_is_not_logged(all_logs):
    """PostgreSQL's own DETAIL quotes the conflicting value; hide_parameters does not remove it."""
    make_account("customer", EMAIL, name=NAME)
    with pytest.raises(DBAPIError) as caught:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO accounts (email, role, full_name) VALUES (:e, 'customer', :n)"),
                         {"e": EMAIL, "n": NAME})
    exc = caught.value
    assert EMAIL in str(exc)  # the raw exception text does contain the value...

    description = describe_exception(exc)  # ...the logged description does not
    _assert_clean(description)
    assert "sqlstate=23505" in description
    assert "table_name=accounts" in description and "constraint_name=accounts_email_key" in description


def test_non_database_errors_are_logged_by_type_and_location_only(all_logs, monkeypatch):
    def explode(*args, **kwargs):
        raise ValueError(f"could not process booking for {NAME} <{EMAIL}>")

    monkeypatch.setattr(booking_service, "validate_request", explode)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/bookings", json=booking_payload(full_name=NAME, email=EMAIL))

    assert response.status_code == 500
    _assert_clean(response.text)
    _assert_clean(all_logs.text)
    line = next(r.getMessage() for r in all_logs.records if r.name == "wendy.errors")
    assert "type=builtins.ValueError" in line and "explode" in line


def test_expected_errors_still_use_normal_responses(all_logs):
    """The catch-all must not swallow validation, auth or rate-limit answers."""
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/api/bookings", json=booking_payload(full_name=" ")).status_code == 422
    assert client.get("/api/staff/bookings").status_code == 401
    assert client.get("/api/nothing-here").status_code == 404
    assert not [r for r in all_logs.records if r.name == "wendy.errors"]
