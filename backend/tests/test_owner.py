import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Booking, Owner, OwnerSession
from app.routers.owner import router as owner_router
from app.security import hash_password

from .conftest import OWNER_EMAIL, OWNER_PASSWORD, booking_payload, future_date

SETTINGS = {
    "booking_enabled": True,
    "owner_confirmed": True,
    "min_party_size": 2,
    "max_party_size": 4,
    "min_lead_minutes": 60,
    "max_advance_days": 14,
    "slot_interval_minutes": 60,
    "windows": [{"weekday": d, "start_time": "09:00", "end_time": "12:00"} for d in range(7)],
}

OWNER_ROUTES = [
    ("GET", "/api/owner/bookings", None),
    ("GET", "/api/owner/bookings/1", None),
    ("POST", "/api/owner/bookings/1/status", {"status": "confirmed"}),
    ("PATCH", "/api/owner/bookings/1", {"internal_notes": "x"}),
    ("GET", "/api/owner/settings", None),
    ("PUT", "/api/owner/settings", SETTINGS),
    ("GET", "/api/owner/menu", None),
    ("POST", "/api/owner/menu/categories", {"name": "Specials"}),
    ("PATCH", "/api/owner/menu/categories/1", {"name": "Renamed"}),
    ("DELETE", "/api/owner/menu/categories/1", None),
    ("POST", "/api/owner/menu/items", {"category_id": 1, "name": "Test item"}),
    ("PATCH", "/api/owner/menu/items/1", {"name": "Renamed"}),
    ("DELETE", "/api/owner/menu/items/1", None),
    ("GET", "/api/auth/me", None),
    ("POST", "/api/auth/logout", None),
]


def make_booking(client, **overrides) -> int:
    reference = client.post("/api/bookings", json=booking_payload(**overrides)).json()["reference"]
    from app.database import SessionLocal

    with SessionLocal() as db:
        return db.scalar(select(Booking.id).where(Booking.reference == reference))


# ---------- access control ----------


@pytest.mark.parametrize("method,path,body", OWNER_ROUTES)
def test_owner_routes_reject_anonymous_requests(client, db, method, path, body):
    before = client.get("/api/menu").json()

    response = client.request(method, path, json=body)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert client.get("/api/menu").json() == before  # nothing was changed


def test_every_owner_route_is_covered_by_the_access_test():
    declared = {
        (method, route.path)
        for route in owner_router.routes
        for method in route.methods - {"HEAD", "OPTIONS"}
    }
    tested = {(m, p.replace("/1", "/{booking_id}", 1)) for m, p, _ in OWNER_ROUTES if "/bookings" in p}
    tested |= {(m, p.replace("/1", "/{category_id}")) for m, p, _ in OWNER_ROUTES if "/categories" in p}
    tested |= {(m, p.replace("/1", "/{item_id}")) for m, p, _ in OWNER_ROUTES if "/items" in p}
    tested |= {(m, p) for m, p, _ in OWNER_ROUTES}
    assert len(declared) == 13 and declared <= tested


def test_forged_or_expired_session_cookie_is_rejected(owner_client, db):
    with TestClient(app) as forged:
        forged.cookies.set("wendy_session", "not-a-real-token")
        assert forged.get("/api/owner/bookings").status_code == 401

    session = db.scalar(select(OwnerSession))
    session.expires_at = session.created_at
    db.commit()
    assert owner_client.get("/api/owner/bookings").status_code == 401


def test_deactivated_owner_loses_access(owner_client, db):
    db.scalar(select(Owner)).is_active = False
    db.commit()
    assert owner_client.get("/api/owner/bookings").status_code == 401


def test_state_changing_requests_need_the_csrf_token(owner_client, client):
    booking_id = make_booking(client)
    del owner_client.headers["X-CSRF-Token"]

    response = owner_client.post(f"/api/owner/bookings/{booking_id}/status", json={"status": "confirmed"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"

    owner_client.headers["X-CSRF-Token"] = "wrong"
    assert owner_client.put("/api/owner/settings", json=SETTINGS).status_code == 403
    assert owner_client.get(f"/api/owner/bookings/{booking_id}").json()["status"] == "pending"


def test_cross_site_origin_is_refused(owner_client, client):
    booking_id = make_booking(client)
    response = owner_client.post(
        f"/api/owner/bookings/{booking_id}/status",
        json={"status": "confirmed"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "bad_origin"


# ---------- login ----------


def test_login_sets_a_hardened_cookie_and_hashes_the_password(owner_client, db):
    owner = db.scalar(select(Owner))
    assert owner.password_hash.startswith("$argon2id$")
    assert OWNER_PASSWORD not in owner.password_hash

    with TestClient(app) as c:
        response = c.post("/api/auth/login", json={"email": OWNER_EMAIL.upper(), "password": OWNER_PASSWORD})
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        token = c.cookies.get("wendy_session")
    # Only a digest of the token is stored.
    assert token not in {s.token_hash for s in db.scalars(select(OwnerSession))}


def test_wrong_password_and_unknown_email_get_the_same_answer(client, db):
    db.add(Owner(email=OWNER_EMAIL, password_hash=hash_password(OWNER_PASSWORD)))
    db.commit()

    wrong = client.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": "wrong password here"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.test", "password": OWNER_PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers


def test_login_is_rate_limited(client, db):
    db.add(Owner(email=OWNER_EMAIL, password_hash=hash_password(OWNER_PASSWORD)))
    db.commit()
    attempt = {"email": OWNER_EMAIL, "password": "wrong password here"}

    statuses = [client.post("/api/auth/login", json=attempt).status_code for _ in range(6)]
    assert statuses == [401] * 5 + [429]
    # Even the right password is refused while locked out.
    assert client.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}).status_code == 429


def test_logout_ends_the_session(owner_client):
    assert owner_client.get("/api/auth/me").json()["email"] == OWNER_EMAIL
    assert owner_client.post("/api/auth/logout").status_code == 204
    assert owner_client.get("/api/owner/bookings").status_code == 401


# ---------- booking management ----------


def test_owner_sees_booking_details_and_filters(owner_client, client):
    first = make_booking(client)
    make_booking(client, requested_date=future_date(5).isoformat(), full_name="Later Guest")
    owner_client.post(f"/api/owner/bookings/{first}/status", json={"status": "confirmed"})

    everything = owner_client.get("/api/owner/bookings").json()
    assert everything["total"] == 2
    assert everything["counts"] == {"pending": 1, "confirmed": 1, "declined": 0, "cancelled": 0}
    detail = everything["items"][0]
    assert detail["full_name"] == "Test Guest" and detail["phone"] == "+9779812345678"
    assert detail["special_requests"] == "Window seat if possible"

    pending = owner_client.get("/api/owner/bookings", params={"status": "pending"}).json()
    assert [b["full_name"] for b in pending["items"]] == ["Later Guest"]

    day = future_date().isoformat()
    by_date = owner_client.get("/api/owner/bookings", params={"date_from": day, "date_to": day}).json()
    assert [b["id"] for b in by_date["items"]] == [first]

    assert owner_client.get("/api/owner/bookings", params={"status": "bogus"}).status_code == 422


@pytest.mark.parametrize("action", ["confirmed", "declined", "cancelled"])
def test_owner_can_confirm_decline_or_cancel_a_pending_request(owner_client, client, db, action):
    booking_id = make_booking(client)

    response = owner_client.post(f"/api/owner/bookings/{booking_id}/status", json={"status": action})

    assert response.status_code == 200
    assert response.json()["status"] == action
    stored = db.get(Booking, booking_id)
    assert stored.status == action and stored.status_changed_at is not None


def test_status_transitions_are_enforced(owner_client, client):
    booking_id = make_booking(client)
    url = f"/api/owner/bookings/{booking_id}/status"

    assert owner_client.post(url, json={"status": "pending"}).status_code == 422
    assert owner_client.post(url, json={"status": "confirmed"}).status_code == 200
    assert owner_client.post(url, json={"status": "declined"}).status_code == 409  # confirmed -> declined
    assert owner_client.post(url, json={"status": "cancelled"}).status_code == 200  # confirmed -> cancelled
    assert owner_client.post(url, json={"status": "confirmed"}).status_code == 409  # cancelled is final
    assert owner_client.post("/api/owner/bookings/99999/status", json={"status": "confirmed"}).status_code == 404


def test_internal_notes_are_saved_and_never_public(owner_client, client):
    booking_id = make_booking(client)

    response = owner_client.patch(f"/api/owner/bookings/{booking_id}", json={"internal_notes": "Regular guest"})
    assert response.json()["internal_notes"] == "Regular guest"
    # Notes cannot be used to change the status.
    sneaky = owner_client.patch(f"/api/owner/bookings/{booking_id}", json={"status": "confirmed"})
    assert sneaky.status_code == 422
    assert owner_client.get(f"/api/owner/bookings/{booking_id}").json()["status"] == "pending"


# ---------- settings ----------


def test_owner_configured_limits_apply_to_new_requests(owner_client, client):
    assert owner_client.get("/api/owner/settings").json()["owner_confirmed"] is False

    response = owner_client.put("/api/owner/settings", json=SETTINGS)
    assert response.status_code == 200
    assert response.json()["max_party_size"] == 4

    config = client.get("/api/booking/config").json()
    assert (config["min_party_size"], config["max_party_size"]) == (2, 4)

    assert client.post("/api/bookings", json=booking_payload(party_size=5)).status_code == 422
    assert client.post("/api/bookings", json=booking_payload(party_size=1)).status_code == 422
    assert client.post("/api/bookings", json=booking_payload(requested_time="13:00")).status_code == 422
    assert client.post("/api/bookings", json=booking_payload(requested_time="09:30")).status_code == 422
    assert client.post("/api/bookings", json=booking_payload(party_size=4, requested_time="11:00")).status_code == 201


@pytest.mark.parametrize(
    "change",
    [
        {"min_party_size": 6, "max_party_size": 2},
        {"slot_interval_minutes": 7},
        {"windows": [{"weekday": 0, "start_time": "12:00", "end_time": "09:00"}]},
        {"windows": [
            {"weekday": 0, "start_time": "09:00", "end_time": "12:00"},
            {"weekday": 0, "start_time": "11:00", "end_time": "14:00"},
        ]},
        {"windows": [{"weekday": 7, "start_time": "09:00", "end_time": "12:00"}]},
    ],
)
def test_invalid_settings_are_rejected(owner_client, change):
    assert owner_client.put("/api/owner/settings", json={**SETTINGS, **change}).status_code == 422
    assert owner_client.get("/api/owner/settings").json()["max_party_size"] == 8


# ---------- menu ----------


def test_seeded_menu_has_documented_items_and_no_prices(client):
    categories = client.get("/api/menu").json()["categories"]
    assert [c["name"] for c in categories] == ["Juices & drinks", "Bowls & breakfast", "Coffee & bites"]
    items = [i for c in categories for i in c["items"]]
    names = {i["name"] for i in items}
    assert {"Banana lassi", "Strawberry lemonade", "Mango smoothie bowl", "Vegan Buddha bowl",
            "Chicken Buddha bowl", "Vegan breakfast", "Sandwiches", "Cakes"} <= names
    assert all(i["price_npr"] is None for i in items)
    assert {i["source"] for i in items} == {"listing", "menu_photo"}


def test_owner_can_edit_the_menu(owner_client, client):
    category = owner_client.post("/api/owner/menu/categories", json={"name": "Seasonal specials"}).json()
    assert category["slug"] == "seasonal-specials"

    item = owner_client.post(
        "/api/owner/menu/items",
        json={"category_id": category["id"], "name": "Lychee juice", "price_npr": "250"},
    ).json()
    assert item["source"] == "owner" and float(item["price_npr"]) == 250

    updated = owner_client.patch(
        f"/api/owner/menu/items/{item['id']}",
        json={"description": "In season", "is_available": False, "price_npr": None},
    ).json()
    assert updated["is_available"] is False and updated["price_npr"] is None

    public = client.get("/api/menu").json()["categories"]
    special = next(c for c in public if c["id"] == category["id"])
    assert special["items"][0]["description"] == "In season"

    assert owner_client.post("/api/owner/menu/items", json={"category_id": 99999, "name": "x"}).status_code == 422
    assert owner_client.post(
        "/api/owner/menu/items", json={"category_id": category["id"], "name": "x", "price_npr": -5}
    ).status_code == 422

    # A category with items cannot be removed by accident.
    assert owner_client.delete(f"/api/owner/menu/categories/{category['id']}").status_code == 409
    assert owner_client.delete(f"/api/owner/menu/items/{item['id']}").status_code == 204
    assert owner_client.delete(f"/api/owner/menu/categories/{category['id']}").status_code == 204
