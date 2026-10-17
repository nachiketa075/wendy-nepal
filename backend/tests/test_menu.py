import json

from sqlalchemy import select, text

from app.menu_import import DEFAULT_FILE, import_menu
from app.models import MenuCategory, MenuItem

from .conftest import employee_client


def public_items(client) -> dict:
    return {i["slug"] or i["name"]: i for c in client.get("/api/menu").json()["categories"] for i in c["items"]}


def test_dry_run_reports_and_writes_nothing(db):
    summary = import_menu(db, apply=False)

    assert summary.applied is False
    assert len(summary.categories_created) == 13 and len(summary.items_created) == 79
    assert set(summary.flagged_for_review) == {"brunch-vegan-porridge", "brunch-cheese-frittata",
                                               "rice-bowl-vegan-buddha-bowl", "rice-bowl-chicken-buddha-bowl"}
    assert summary.legacy_items_visible == 25
    assert "DRY RUN" in summary.lines()[0]
    assert db.execute(text("SELECT count(*) FROM menu_items WHERE source = 'owner_pdf'")).scalar() == 0


def test_import_matches_the_printed_menu_and_keeps_its_order(db, client):
    import_menu(db, apply=True, hide_legacy=True)
    source = json.loads(DEFAULT_FILE.read_text())

    menu = client.get("/api/menu").json()["categories"]
    assert [c["name"] for c in menu] == [c["name"] for c in source["categories"]]
    assert sum(len(c["items"]) for c in menu) == 79
    brunch = next(c for c in menu if c["slug"] == "brunch")
    assert [i["name"] for i in brunch["items"]][:2] == ["Simple Breakfast", "Vegan Breakfast"]
    simple = brunch["items"][0]
    assert float(simple["price_npr"]) == 450 and simple["addons"] == [{"label": "add on sausages", "price": 80, "unit": "per piece"}]
    sandwiches = next(c for c in menu if c["slug"] == "sandwiches")
    assert sandwiches["notes"] == [{"label": "Extra Cheese Topping", "price": 70, "prefix": "+"}]
    # Supplied wording is preserved, including the entries flagged for the owner.
    items = public_items(client)
    assert items["brunch-vegan-porridge"]["description"] == "Sourdough Toast, Avocado, Cherry Tomatoes"
    assert items["rice-bowl-vegan-buddha-bowl"]["name"] == "Vegan Buddha Bowl"
    assert "sausages" in items["brunch-cheese-frittata"]["description"]
    assert "review_note" not in items["brunch-vegan-porridge"]  # internal note stays internal


def test_import_is_repeatable(db):
    import_menu(db, apply=True)
    again = import_menu(db, apply=True)

    assert again.items_created == [] and again.items_updated == [] and again.categories_created == []
    assert again.items_unchanged == 79
    assert db.execute(text("SELECT count(*) FROM menu_items WHERE source = 'owner_pdf'")).scalar() == 79
    assert db.execute(text("SELECT count(*) FROM menu_categories")).scalar() == 16  # 3 older + 13 imported


def test_owner_edits_survive_a_re_import_and_file_changes_reach_untouched_items(db, owner_client, tmp_path):
    import_menu(db, apply=True)
    staff = {i["slug"]: i for c in owner_client.get("/api/staff/menu").json()["categories"] for i in c["items"]}
    edited, untouched = staff["coffee-espresso"], staff["coffee-doppio"]
    assert edited["edited_since_import"] is False and edited["source"] == "owner_pdf"

    owner_client.patch(f"/api/staff/menu/items/{edited['id']}", json={"price_npr": "175", "description": "Owner's wording"})

    changed = json.loads(DEFAULT_FILE.read_text())
    coffee = changed["categories"][0]["items"]
    coffee[0]["price_npr"], coffee[1]["price_npr"] = 999, 185  # espresso, doppio
    path = tmp_path / "menu.json"
    path.write_text(json.dumps(changed))
    summary = import_menu(db, path=path, apply=True)

    assert summary.items_kept_owner_edit == ["coffee-espresso"] and summary.items_updated == ["coffee-doppio"]
    db.expire_all()
    espresso = db.scalar(select(MenuItem).where(MenuItem.slug == "coffee-espresso"))
    assert float(espresso.price_npr) == 175 and espresso.description == "Owner's wording"
    assert float(db.get(MenuItem, untouched["id"]).price_npr) == 185
    after = {i["slug"]: i for c in owner_client.get("/api/staff/menu").json()["categories"] for i in c["items"]}
    assert after["coffee-espresso"]["edited_since_import"] is True


def test_hiding_legacy_items_keeps_them_for_the_owner(db, client, owner_client):
    summary = import_menu(db, apply=True, hide_legacy=True)

    assert summary.legacy_items_hidden == 25
    assert "Banana lassi" not in {i["name"] for i in public_items(client).values() if i["slug"] is None}
    legacy = [i for c in owner_client.get("/api/staff/menu").json()["categories"] for i in c["items"] if i["source"] == "listing"]
    assert legacy and all(i["is_published"] is False for i in legacy)
    assert db.execute(text("SELECT count(*) FROM menu_items WHERE source IN ('listing', 'menu_photo')")).scalar() == 25


def test_public_and_owner_menus_are_the_same_rows(db, client, owner_client):
    import_menu(db, apply=True, hide_legacy=True)
    category = owner_client.post("/api/staff/menu/categories", json={"name": "Seasonal specials", "sort_order": 999}).json()
    item = owner_client.post("/api/staff/menu/items", json={
        "category_id": category["id"], "name": "Lychee juice", "price_npr": "250",
        "addons": [{"label": "extra shot", "price": "40"}]}).json()

    shown = public_items(client)["Lychee juice"]
    assert shown["id"] == item["id"] and float(shown["price_npr"]) == 250
    assert shown["addons"] == [{"label": "extra shot", "price": 40.0}]

    owner_client.patch(f"/api/staff/menu/items/{item['id']}", json={"name": "Fresh lychee juice", "is_available": False})
    assert public_items(client)["Fresh lychee juice"]["is_available"] is False

    owner_client.patch(f"/api/staff/menu/items/{item['id']}", json={"is_published": False})
    assert "Fresh lychee juice" not in public_items(client)
    assert "seasonal-specials" not in {c["slug"] for c in client.get("/api/menu").json()["categories"]}  # empty sections hidden

    assert owner_client.delete(f"/api/staff/menu/categories/{category['id']}").status_code == 409
    assert owner_client.delete(f"/api/staff/menu/items/{item['id']}").status_code == 204
    assert owner_client.delete(f"/api/staff/menu/categories/{category['id']}").status_code == 204


def test_menu_editing_needs_the_menu_permission(db):
    category_id = db.scalar(select(MenuCategory.id))
    viewer = employee_client(["bookings.view_all"], "viewer@example.com")
    assert viewer.get("/api/staff/menu").status_code == 403
    assert viewer.post("/api/staff/menu/items", json={"category_id": category_id, "name": "x"}).status_code == 403

    editor = employee_client(["menu.manage"])
    created = editor.post("/api/staff/menu/items", json={"category_id": category_id, "name": "Staff special"})
    assert created.status_code == 201
    assert editor.post("/api/staff/menu/items", json={"category_id": category_id, "name": "x", "price_npr": -5}).status_code == 422
    assert editor.post("/api/staff/menu/items", json={"category_id": 99999, "name": "x"}).status_code == 422
    assert editor.get("/api/staff/bookings").status_code == 403  # menu access is not booking access
