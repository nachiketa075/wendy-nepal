"""Seed PROVISIONAL booking settings and the publicly documented menu.

Everything inserted here is a starting point the owner must review:

* Booking windows, party sizes and lead times are demo values. They are NOT
  taken from any listing's opening hours (which disagree with each other).
  `owner_confirmed` starts false, and production refuses booking requests
  until the owner confirms the settings in the dashboard.
* Menu items come from public listings ("listing") or from the chalkboard in a
  guest photo ("menu_photo"). No prices are seeded: the prices visible in that
  photo are of unknown date and must not be shown as current.

Revision ID: 0002
Revises: 0001
"""
import datetime as dt

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CATEGORIES = [
    ("drinks", "Juices & drinks", "Sip something fresh"),
    ("bowls", "Bowls & breakfast", "By the spoonful"),
    ("bites", "Coffee & bites", "A little comfort"),
]

L, P = "listing", "menu_photo"
BOARD = "On the menu board in a guest photo: "

# (category slug, name, description, source)
ITEMS = [
    ("drinks", "Fresh fruit juices", "Freshly pressed fruit, a little sunshine in a glass. " + BOARD
     + "banana, watermelon, pineapple, papaya, apple, sweet lemon, avocado, orange, cucumber, mango, "
     "strawberry, or mixed.", L),
    ("drinks", "Banana lassi", "A creamy, fruity favourite for a relaxed afternoon.", L),
    ("drinks", "Strawberry lemonade", "A bright, refreshing break from your Lakeside walk.", L),
    ("drinks", "Milkshakes", "Ask which fruits are in season today.", L),
    ("drinks", "ABC juice", BOARD + "apple, beetroot, carrot.", P),
    ("drinks", "Fresh lemonade & mint lemonade", None, P),
    ("drinks", "Tea", BOARD + "black, lemon, milk, masala, holy basil and green tea; hot lemon; "
     "hot lemon honey; ginger lemon honey.", P),
    ("bowls", "Mango smoothie bowl", BOARD + "smoothie with granola, fruits and dry fruits topping.", L),
    ("bowls", "Strawberry smoothie bowl", BOARD + "smoothie with granola, fruits and dry fruits topping.", L),
    ("bowls", "Papaya smoothie bowl", BOARD + "smoothie with granola, fruits and dry fruits topping.", P),
    ("bowls", "Avocado smoothie bowl", BOARD + "smoothie with granola, fruits and dry fruits topping.", P),
    ("bowls", "Fruit bowls & fruit salad", "Fresh fruit for a colourful start. " + BOARD
     + "fruit salad; fruit with yogurt.", L),
    ("bowls", "Yogurt, granola & muesli", BOARD + "muesli fruit yogurt; granola fruit yogurt.", L),
    ("bowls", "Porridge & oats with fruit", None, P),
    ("bowls", "Vegan Buddha bowl", BOARD + "chickpeas, sliced vegetables, quinoa, with sauce.", L),
    ("bowls", "Chicken Buddha bowl", BOARD + "chickpeas, sliced vegetables, quinoa, with sauce.", L),
    ("bowls", "Vegan breakfast", BOARD + "2 toast, peanut butter, jam, fried tofu with mushroom & "
     "spinach, fruit salad.", L),
    ("bowls", "Light breakfast", BOARD + "2 toast, butter, jam/honey, 2 eggs, fruit salad.", P),
    ("bowls", "Simple breakfast", BOARD + "2 toast, butter, jam/honey, 2 eggs, fried potatoes, fruits.", P),
    ("bowls", "Trekker's breakfast", BOARD + "2 toast, butter, jam/honey, 2 eggs, fried potatoes, "
     "fruits, sausage/bacon.", P),
    ("bites", "Coffee & lattes", "A familiar favourite, from your first cup to an afternoon break. " + BOARD
     + "espresso, doppio, americano, lungo, cappuccino, cafe latte, cafe mocha, flat white, and iced "
     "americano, cappuccino, latte and mocha. Vegan option with oat milk.", L),
    ("bites", "Sandwiches", "An easy bite for breakfast, lunch or somewhere in between. " + BOARD
     + "veg; cheese/tuna; chicken/egg; bacon/ham.", L),
    ("bites", "Cakes", "A little sweetness to round out your visit. Ask what is fresh today.", L),
    ("bites", "Toast & smashed avocado", BOARD + "2 toast with butter, jam/honey; smashed avocado with "
     "toast; smashed avocado toast with egg.", P),
    ("bites", "Eggs & omelettes", BOARD + "2 boiled eggs; plain, masala or cheese omelette.", P),
]


def upgrade() -> None:
    settings = sa.table(
        "booking_settings",
        *(sa.column(c) for c in ("id", "booking_enabled", "owner_confirmed", "min_party_size",
                                 "max_party_size", "min_lead_minutes", "max_advance_days",
                                 "slot_interval_minutes")),
    )
    # PROVISIONAL demo values - the owner must review them in the dashboard.
    op.bulk_insert(settings, [{
        "id": 1, "booking_enabled": True, "owner_confirmed": False, "min_party_size": 1,
        "max_party_size": 8, "min_lead_minutes": 120, "max_advance_days": 30, "slot_interval_minutes": 30,
    }])

    windows = sa.table("booking_windows", sa.column("weekday"), sa.column("start_time"), sa.column("end_time"))
    op.bulk_insert(windows, [
        {"weekday": day, "start_time": dt.time(8, 0), "end_time": dt.time(18, 0)} for day in range(7)
    ])

    categories = sa.table("menu_categories", *(sa.column(c) for c in ("slug", "name", "tagline", "sort_order")))
    op.bulk_insert(categories, [
        {"slug": slug, "name": name, "tagline": tagline, "sort_order": i * 10}
        for i, (slug, name, tagline) in enumerate(CATEGORIES)
    ])

    conn = op.get_bind()
    ids = dict(conn.execute(sa.text("SELECT slug, id FROM menu_categories")).all())
    items = sa.table(
        "menu_items",
        *(sa.column(c) for c in ("category_id", "name", "description", "source", "sort_order", "is_available")),
    )
    op.bulk_insert(items, [
        {"category_id": ids[slug], "name": name, "description": description, "source": source,
         "sort_order": i * 10, "is_available": True}
        for i, (slug, name, description, source) in enumerate(ITEMS)
    ])


def downgrade() -> None:
    op.execute("DELETE FROM menu_items WHERE source IN ('listing', 'menu_photo')")
    op.execute("DELETE FROM menu_categories WHERE slug IN ('drinks', 'bowls', 'bites') "
               "AND NOT EXISTS (SELECT 1 FROM menu_items WHERE category_id = menu_categories.id)")
    op.execute("DELETE FROM booking_windows")
    op.execute("DELETE FROM booking_settings")
