import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import booking_service
from app.main import app
from app.models import Booking

from .conftest import OWNER_EMAIL, booking_payload, booking_id_for, future_date, make_account, make_booking, sign_in

FORBIDDEN_KEYS = {"internal_notes", "assigned_employee", "assigned_employee_id", "history", "version", "id", "customer_id"}


def test_customer_booking_is_pending_linked_and_uses_server_values(customer_client, db):
    response = customer_client.post("/api/customer/bookings", json=booking_payload())

    assert response.status_code == 201
    assert response.json()["message"] == booking_service.RECEIVED_MESSAGE and response.json()["status"] == "pending"
    booking = db.scalar(select(Booking))
    assert booking.status == "pending" and booking.customer_id == 1 and booking.assigned_employee_id is None

    for field, value in (("customer_id", 99), ("status", "confirmed"), ("reference", "WJ-MINE"),
                         ("assigned_employee_id", 1), ("internal_notes", "vip")):
        refused = customer_client.post("/api/customer/bookings", json=booking_payload(requested_time="11:00", **{field: value}))
        assert refused.status_code == 422, field
    assert db.query(Booking).count() == 1


def test_customer_endpoints_need_a_customer_session(client, owner_client):
    for c, expected in ((client, 401), (owner_client, 403)):
        assert c.get("/api/customer/bookings").status_code == expected
        assert c.post("/api/customer/bookings", json=booking_payload()).status_code == expected


def test_customer_sees_only_their_own_bookings(customer_client):
    make_account("customer", "customer.b@example.com", name="Customer B")
    other = sign_in("customer.b@example.com")
    mine = customer_client.post("/api/customer/bookings", json=booking_payload()).json()["reference"]
    theirs = other.post("/api/customer/bookings", json=booking_payload(phone="+977 9800000002")).json()["reference"]

    listed = customer_client.get("/api/customer/bookings").json()
    assert [b["reference"] for b in listed["items"]] == [mine] and listed["total"] == 1
    assert customer_client.get(f"/api/customer/bookings/{mine}").status_code == 200

    # B's booking is invisible to A for reading and for changing.
    assert customer_client.get(f"/api/customer/bookings/{theirs}").status_code == 404
    assert customer_client.post(f"/api/customer/bookings/{theirs}/cancellation-request", json={}).status_code == 404
    assert other.get(f"/api/customer/bookings/{theirs}").json()["cancellation"] is None


def test_customer_response_has_no_internal_fields(customer_client, owner_client):
    booking_id = make_booking(customer_client, "/api/customer/bookings")
    owner_client.patch(f"/api/staff/bookings/{booking_id}", json={"internal_notes": "SECRET staff note", "version": 1})

    listed = customer_client.get("/api/customer/bookings")
    detail = customer_client.get(f"/api/customer/bookings/{listed.json()['items'][0]['reference']}")
    for response in (listed, detail):
        assert "SECRET" not in response.text
    assert not FORBIDDEN_KEYS & set(detail.json())


def test_guest_bookings_are_never_claimed_by_matching_contact_details(client, db):
    guest_ref = client.post("/api/bookings", json=booking_payload(email="same@example.com")).json()["reference"]

    registered = TestClient(app)
    registered.post("/api/auth/register", json={"full_name": "Same Person", "email": "same@example.com",
                                                "password": "a long enough password", "phone": "+977 9812345678"})
    registered.headers["X-CSRF-Token"] = registered.get("/api/auth/me").json()["csrf_token"]

    assert registered.get("/api/customer/bookings").json()["total"] == 0
    assert registered.get(f"/api/customer/bookings/{guest_ref}").status_code == 404
    assert db.scalar(select(Booking)).customer_id is None


def test_pagination_and_upcoming_past_split(customer_client, owner_client):
    ids = [make_booking(customer_client, "/api/customer/bookings", requested_time=f"{9 + i:02d}:00") for i in range(3)]
    owner_client.post(f"/api/staff/bookings/{ids[0]}/status", json={"status": "declined", "version": 1})

    page = customer_client.get("/api/customer/bookings", params={"limit": 2, "offset": 0}).json()
    assert len(page["items"]) == 2 and page["total"] == 3 and page["limit"] == 2
    assert len(customer_client.get("/api/customer/bookings", params={"limit": 2, "offset": 2}).json()["items"]) == 1
    assert customer_client.get("/api/customer/bookings", params={"limit": 500}).status_code == 422

    assert customer_client.get("/api/customer/bookings", params={"when": "upcoming"}).json()["total"] == 2
    past = customer_client.get("/api/customer/bookings", params={"when": "past"}).json()
    assert [b["status"] for b in past["items"]] == ["declined"]


def test_customer_idempotency_and_conflict(customer_client, db):
    key = str(uuid.uuid4())
    first = customer_client.post("/api/customer/bookings", json=booking_payload(idempotency_key=key))
    replay = customer_client.post("/api/customer/bookings", json=booking_payload(idempotency_key=key))
    changed = customer_client.post("/api/customer/bookings", json=booking_payload(idempotency_key=key, party_size=6))

    assert (first.status_code, replay.status_code, changed.status_code) == (201, 200, 409)
    assert replay.json()["reference"] == first.json()["reference"]
    assert db.query(Booking).count() == 1


def test_a_key_used_by_someone_else_does_not_expose_their_booking(customer_client, client):
    key = str(uuid.uuid4())
    client.post("/api/bookings", json=booking_payload(idempotency_key=key))
    response = customer_client.post("/api/customer/bookings", json=booking_payload(idempotency_key=key))
    assert response.status_code == 409


# ---------- cancellation requests ----------


def test_cancellation_request_does_not_cancel_by_itself(customer_client, db):
    ref = customer_client.post("/api/customer/bookings", json=booking_payload()).json()["reference"]

    response = customer_client.post(f"/api/customer/bookings/{ref}/cancellation-request", json={"reason": "Plans changed"})

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "pending"  # still the booking's own status
    assert body["cancellation"]["status"] == "pending" and body["can_request_cancellation"] is False
    assert db.scalar(select(Booking)).status == "pending"
    assert customer_client.post(f"/api/customer/bookings/{ref}/cancellation-request", json={}).status_code == 409


def test_staff_approve_a_cancellation_and_the_customer_sees_it(customer_client, owner_client):
    ref = customer_client.post("/api/customer/bookings", json=booking_payload()).json()["reference"]
    customer_client.post(f"/api/customer/bookings/{ref}/cancellation-request", json={"reason": "Plans changed"})
    booking_id = booking_id_for(ref)

    queue = owner_client.get("/api/staff/bookings", params={"cancellation": "pending"}).json()
    assert [b["id"] for b in queue["items"]] == [booking_id]
    assert queue["items"][0]["cancellation"]["reason"] == "Plans changed"
    assert owner_client.get("/api/staff/alerts").json()["cancellation_requests"] == 1

    resolved = owner_client.post(f"/api/staff/bookings/{booking_id}/cancellation",
                                 json={"decision": "approve", "version": queue["items"][0]["version"], "response": "No problem."})
    assert resolved.status_code == 200 and resolved.json()["status"] == "cancelled"

    mine = customer_client.get(f"/api/customer/bookings/{ref}").json()
    assert mine["status"] == "cancelled"
    assert mine["cancellation"]["status"] == "approved" and mine["cancellation"]["response"] == "No problem."
    assert mine["can_request_cancellation"] is False


def test_staff_decline_a_cancellation_and_the_booking_stays(customer_client, owner_client):
    ref = customer_client.post("/api/customer/bookings", json=booking_payload()).json()["reference"]
    booking_id = booking_id_for(ref)
    owner_client.post(f"/api/staff/bookings/{booking_id}/status", json={"status": "confirmed", "version": 1})
    customer_client.post(f"/api/customer/bookings/{ref}/cancellation-request", json={})
    version = owner_client.get(f"/api/staff/bookings/{booking_id}").json()["version"]

    declined = owner_client.post(f"/api/staff/bookings/{booking_id}/cancellation",
                                 json={"decision": "decline", "version": version, "response": "Please call us."})
    assert declined.json()["status"] == "confirmed"

    mine = customer_client.get(f"/api/customer/bookings/{ref}").json()
    assert mine["status"] == "confirmed" and mine["cancellation"]["status"] == "declined"
    assert mine["can_request_cancellation"] is True  # they may ask again
    again = owner_client.post(f"/api/staff/bookings/{booking_id}/cancellation", json={"decision": "approve", "version": version + 1})
    assert again.status_code == 409  # nothing open to resolve


def test_cancellation_cannot_be_requested_for_finished_bookings(customer_client, owner_client):
    ref = customer_client.post("/api/customer/bookings", json=booking_payload()).json()["reference"]
    owner_client.post(f"/api/staff/bookings/{booking_id_for(ref)}/status", json={"status": "declined", "version": 1})
    response = customer_client.post(f"/api/customer/bookings/{ref}/cancellation-request", json={})
    assert response.status_code == 409 and response.json()["error"]["code"] == "not_cancellable"
