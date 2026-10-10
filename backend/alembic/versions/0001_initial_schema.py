"""Initial schema: owners, sessions, bookings, booking settings, menu.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_now = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "owners",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now),
    )
    op.create_table(
        "owner_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_owner_sessions_owner_id", "owner_sessions", ["owner_id"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reference", sa.String(16), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True, unique=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("requested_date", sa.Date, nullable=False),
        sa.Column("requested_time", sa.Time, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("party_size", sa.Integer, nullable=False),
        sa.Column("special_requests", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("internal_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','confirmed','declined','cancelled')", name="ck_bookings_status"),
        sa.CheckConstraint("party_size >= 1", name="ck_bookings_party_size"),
    )
    op.create_index("ix_bookings_requested_date", "bookings", ["requested_date"])
    op.create_index("ix_bookings_status_requested_at", "bookings", ["status", "requested_at"])

    op.create_table(
        "booking_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("booking_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("owner_confirmed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("min_party_size", sa.Integer, nullable=False),
        sa.Column("max_party_size", sa.Integer, nullable=False),
        sa.Column("min_lead_minutes", sa.Integer, nullable=False),
        sa.Column("max_advance_days", sa.Integer, nullable=False),
        sa.Column("slot_interval_minutes", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now),
        sa.CheckConstraint("id = 1", name="ck_booking_settings_singleton"),
        sa.CheckConstraint(
            "min_party_size >= 1 AND max_party_size >= min_party_size", name="ck_booking_settings_party"
        ),
    )
    op.create_table(
        "booking_windows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("weekday", sa.SmallInteger, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_booking_windows_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_booking_windows_order"),
    )
    op.create_index("ix_booking_windows_weekday", "booking_windows", ["weekday"])

    op.create_table(
        "menu_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("tagline", sa.String(80), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "category_id", sa.Integer, sa.ForeignKey("menu_categories.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("price_npr", sa.Numeric(10, 2), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="owner"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("source IN ('listing','menu_photo','owner')", name="ck_menu_items_source"),
        sa.CheckConstraint("price_npr IS NULL OR price_npr >= 0", name="ck_menu_items_price"),
    )
    op.create_index("ix_menu_items_category_id", "menu_items", ["category_id"])


def downgrade() -> None:
    for table in (
        "menu_items",
        "menu_categories",
        "booking_windows",
        "booking_settings",
        "bookings",
        "owner_sessions",
        "owners",
    ):
        op.drop_table(table)
