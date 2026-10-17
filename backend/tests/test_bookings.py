import datetime as dt
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app import booking_service
from app.main import app
from app.models import Booking

from .conftest import booking_payload, future_date


def count_bookings(db) -> int:
    return db.scalar(select(func.count()).select_from(Booking))


# ---------- persistence and response ----------


def test_valid_request_is_persisted_as_pending(client, db):
    response = client.post("/api/bookings", json=booking_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["message"] == booking_service.RECEIVED_MESSAGE
    assert "not confirmed yet" in body["message"]
    assert body["reference"].startswith("WJ-")
    # The receipt carries no guest details.
    assert set(body) == {"reference", "status", "message"}

    stored = db.scalar(select(Booking).where(Booking.reference == body["reference"]))
    assert stored.status == "pending"
    assert stored.full_name == "Test Guest"
    assert stored.phone == "+9779812345678"  # normalised to E.164
    assert stored.party_size == 2
    assert stored.requested_time == dt.time(10, 0)
    # Stored instant is the requested wall-clock time in Asia/Kathmandu (UTC+5:45).
    assert stored.requested_at.astimezone(dt.UTC) == dt.datetime.combine(
        future_date(), dt.time(4, 15), tzinfo=dt.UTC
    )


def test_references_are_generated_by_the_backend_and_unique(client):
    refs = {
        client.post("/api/bookings", json=booking_payload(requested_time=t)).json()["reference"]
        for t in ("10:00", "10:30", "11:00")
    }
    assert len(refs) == 3


@pytest.mark.parametrize("field,value", [("status", "confirmed"), ("reference", "WJ-HACKED"), ("internal_notes", "x")])
def test_customer_cannot_supply_server_controlled_fields(client, db, field, value):
    response = client.post("/api/bookings", json=booking_payload(**{field: value}))

    assert response.status_code == 422
    assert field in response.json()["error"]["fields"]
    assert count_bookings(db) == 0


def test_optional_fields_may_be_blank(client, db):
    response = client.post("/api/bookings", json=booking_payload(email="", special_requests="  "))

    assert response.status_code == 201
    stored = db.scalar(select(Booking))
    assert stored.email is None and stored.special_requests is None


# ---------- validation ----------


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"full_name": " "}, "full_name"),
        ({"phone": "9812345678"}, "phone"),  # no country code
        ({"phone": "+977 12"}, "phone"),
        ({"phone": "+999 123456789"}, "phone"),
        ({"email": "not-an-email"}, "email"),
        ({"party_size": 0}, "party_size"),
        ({"party_size": 9}, "party_size"),  # above the configured maximum of 8
        ({"requested_date": "2024-13-40"}, "requested_date"),
        ({"requested_time": "07:30"}, "requested_time"),  # before the window opens
        ({"requested_time": "18:30"}, "requested_time"),  # after the window closes
        ({"requested_time": "10:10"}, "requested_time"),  # not on a 30-minute slot
        ({"special_requests": "x" * 1001}, "special_requests"),
    ],
)
def test_invalid_requests_are_rejected_and_not_saved(client, db, overrides, field):
    response = client.post("/api/bookings", json=booking_payload(**overrides))

    assert response.status_code == 422, response.text
    assert field in response.json()["error"]["fields"]
    assert count_bookings(db) == 0


@pytest.mark.parametrize("phone", ["+977 985-6031094", "+91 98765 43210", "+44 7911 123456", "+1 415 555 2671"])
def test_nepal_india_and_international_numbers_are_accepted(client, phone):
    assert client.post("/api/bookings", json=booking_payload(phone=phone)).status_code == 201


def test_past_date_is_rejected(client, db):
    response = client.post("/api/bookings", json=booking_payload(requested_date=future_date(-1).isoformat()))

    assert response.status_code == 422
    assert "requested_date" in response.json()["error"]["fields"]
    assert count_bookings(db) == 0


def test_past_time_today_is_judged_in_kathmandu_time(client, db, monkeypatch):
    # 09:00 UTC is already 14:45 in Pokhara, so 10:00 "today" has passed there
    # even though it has not in UTC.
    tz = booking_service.get_settings().tz
    fixed = dt.datetime.combine(future_date(), dt.time(9, 0), tzinfo=dt.UTC).astimezone(tz)
    monkeypatch.setattr(booking_service, "now_local", lambda: fixed)

    response = client.post("/api/bookings", json=booking_payload(requested_time="10:00"))
    assert response.status_code == 422
    assert "requested_date" in response.json()["error"]["fields"]

    # Inside the minimum notice period (2 hours) is also refused...
    response = client.post("/api/bookings", json=booking_payload(requested_time="16:00"))
    assert "requested_time" in response.json()["error"]["fields"]

    # ...while a later slot the same day is fine.
    assert client.post("/api/bookings", json=booking_payload(requested_time="17:00")).status_code == 201
    assert count_bookings(db) == 1


def test_too_far_ahead_is_rejected(client):
    response = client.post("/api/bookings", json=booking_payload(requested_date=future_date(31).isoformat()))
    assert response.status_code == 422
    assert "requested_date" in response.json()["error"]["fields"]


def test_day_without_a_booking_window_is_rejected(client, db):
    day = future_date()
    db.execute(text("DELETE FROM booking_windows WHERE weekday = :d"), {"d": day.weekday()})
    db.commit()

    response = client.post("/api/bookings", json=booking_payload())
    assert response.status_code == 422
    assert "requested_date" in response.json()["error"]["fields"]


def test_requests_refused_when_owner_switches_booking_off(client, db):
    db.execute(text("UPDATE booking_settings SET booking_enabled = false"))
    db.commit()

    assert client.get("/api/booking/config").json()["accepting_requests"] is False
    response = client.post("/api/bookings", json=booking_payload())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "booking_unavailable"
    assert count_bookings(db) == 0


def test_production_requires_owner_confirmed_settings(client, db, monkeypatch):
    monkeypatch.setattr(booking_service.get_settings(), "environment", "production")

    assert client.post("/api/bookings", json=booking_payload()).status_code == 409

    db.execute(text("UPDATE booking_settings SET owner_confirmed = true"))
    db.commit()
    assert client.post("/api/bookings", json=booking_payload()).status_code == 201


# ---------- duplicates ----------


def test_retry_with_same_idempotency_key_does_not_create_a_second_booking(client, db):
    payload = booking_payload(idempotency_key=str(uuid.uuid4()))

    first = client.post("/api/bookings", json=payload)
    second = client.post("/api/bookings", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["reference"] == first.json()["reference"]
    assert count_bookings(db) == 1


def test_identical_request_without_key_is_not_duplicated(client, db):
    first = client.post("/api/bookings", json=booking_payload())
    # Same guest, slot and party size, phone typed differently.
    second = client.post("/api/bookings", json=booking_payload(phone="+9779812345678"))

    assert second.status_code == 200
    assert second.json()["reference"] == first.json()["reference"]
    assert count_bookings(db) == 1


def test_rapid_concurrent_clicks_create_one_booking(db):
    payload = booking_payload(idempotency_key=str(uuid.uuid4()))

    def submit(_):
        with TestClient(app) as c:
            return c.post("/api/bookings", json=payload)

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(submit, range(4)))

    assert all(r.status_code in (200, 201) for r in responses)
    assert len({r.json()["reference"] for r in responses}) == 1
    assert count_bookings(db) == 1


def test_different_slot_is_a_new_request(client, db):
    client.post("/api/bookings", json=booking_payload())
    client.post("/api/bookings", json=booking_payload(requested_time="12:00"))
    assert count_bookings(db) == 2


# ---------- abuse protection and privacy ----------


def test_booking_endpoint_is_rate_limited(client):
    statuses = [
        client.post("/api/bookings", json=booking_payload(requested_time=f"{9 + i:02d}:00")).status_code
        for i in range(6)
    ]
    assert statuses[:5] == [201] * 5
    assert statuses[5] == 429


def test_no_public_endpoint_lists_or_reads_bookings(client):
    reference = client.post("/api/bookings", json=booking_payload()).json()["reference"]

    for path in ("/api/bookings", f"/api/bookings/{reference}", "/api/bookings/1"):
        assert client.get(path).status_code in (404, 405)
    for path in ("/api/staff/bookings", "/api/staff/bookings/1", "/api/customer/bookings"):
        response = client.get(path)
        assert response.status_code == 401
        assert "Test Guest" not in response.text


def test_public_config_exposes_rules_but_no_guest_data(client):
    client.post("/api/bookings", json=booking_payload())
    config = client.get("/api/booking/config").json()

    assert config["timezone"] == "Asia/Kathmandu"
    assert config["accepting_requests"] is True
    assert (config["min_party_size"], config["max_party_size"]) == (1, 8)
    assert len(config["windows"]) == 7
    assert "Test Guest" not in str(config)


def test_reusing_an_idempotency_key_with_different_details_is_a_conflict(client, db):
    key = str(uuid.uuid4())
    assert client.post("/api/bookings", json=booking_payload(idempotency_key=key)).status_code == 201

    changed = client.post("/api/bookings", json=booking_payload(idempotency_key=key, party_size=5))

    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_conflict"
    assert count_bookings(db) == 1
    assert db.scalar(select(Booking)).party_size == 2  # the stored request is untouched


def test_new_request_starts_its_status_history(client, db):
    client.post("/api/bookings", json=booking_payload())
    rows = db.execute(text("SELECT from_status, to_status, actor_role FROM booking_status_history")).all()
    assert rows == [(None, "pending", "guest")]


def test_closed_dates_and_special_day_windows(client, db):
    closed, special = future_date(2), future_date(3)
    db.execute(text("INSERT INTO booking_date_overrides (date, is_closed) VALUES (:d, true)"), {"d": closed})
    db.execute(
        text("INSERT INTO booking_date_overrides (date, is_closed, start_time, end_time) VALUES (:d, false, '12:00', '14:00')"),
        {"d": special},
    )
    db.commit()

    refused = client.post("/api/bookings", json=booking_payload(requested_date=closed.isoformat()))
    assert refused.status_code == 422 and "requested_date" in refused.json()["error"]["fields"]

    outside = client.post("/api/bookings", json=booking_payload(requested_date=special.isoformat(), requested_time="10:00"))
    assert outside.status_code == 422 and "requested_time" in outside.json()["error"]["fields"]
    inside = client.post("/api/bookings", json=booking_payload(requested_date=special.isoformat(), requested_time="13:00"))
    assert inside.status_code == 201

    config = client.get("/api/booking/config").json()
    assert [(o["date"], o["is_closed"]) for o in config["overrides"]] == [(closed.isoformat(), True), (special.isoformat(), False)]
    assert "note" not in config["overrides"][0]


def test_rate_limit_is_shared_through_the_database(client, db):
    """Counters live in PostgreSQL, so they hold across API workers."""
    for i in range(5):
        client.post("/api/bookings", json=booking_payload(requested_time=f"{9 + i:02d}:00"))
    assert db.execute(text("SELECT count(*) FROM rate_limit_events")).scalar() >= 5
    # The stored keys are digests, not addresses.
    assert all(len(k) == 64 for (k,) in db.execute(text("SELECT key_hash FROM rate_limit_events")))
