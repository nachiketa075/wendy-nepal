"""Accounts for owner/employee/customer, booking workflow, shared menu fields.

Additive only. Existing data is preserved:

* Every row in `owners` is copied into the new `accounts` table as an owner,
  with the same email, password hash and active flag, so owners sign in with
  the password they already have.
* `owners` and `owner_sessions` are left in place but are no longer used.
  Sessions move to `account_sessions`, so anyone signed in must sign in again.
* Bookings, references, menu rows and booking settings are untouched apart
  from new nullable/defaulted columns. Each existing booking gets one opening
  entry in the new status history.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_now = sa.text("now()")
tz = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("permissions", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
        sa.CheckConstraint("role IN ('owner','employee','customer')", name="ck_accounts_role"),
    )
    # Carry existing owners over with their credentials.
    op.execute(
        "INSERT INTO accounts (email, password_hash, role, full_name, is_active, created_at) "
        "SELECT lower(email), password_hash, 'owner', 'Owner', is_active, created_at FROM owners"
    )

    op.create_table(
        "account_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
        sa.Column("expires_at", tz, nullable=False),
    )
    op.create_index("ix_account_sessions_account_id", "account_sessions", ["account_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(16), nullable=False, server_default="reset"),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
        sa.Column("expires_at", tz, nullable=False),
        sa.Column("used_at", tz, nullable=True),
    )
    op.create_index("ix_password_reset_tokens_account_id", "password_reset_tokens", ["account_id"])

    # --- bookings ---
    op.add_column("bookings", sa.Column("request_hash", sa.String(64), nullable=True))
    op.add_column("bookings", sa.Column("customer_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("bookings", sa.Column("assigned_employee_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("bookings", sa.Column("version", sa.Integer, nullable=False, server_default="1"))
    op.add_column("bookings", sa.Column("updated_at", tz, nullable=False, server_default=_now))
    op.add_column("bookings", sa.Column("cancellation_status", sa.String(16), nullable=True))
    op.add_column("bookings", sa.Column("cancellation_reason", sa.Text, nullable=True))
    op.add_column("bookings", sa.Column("cancellation_requested_at", tz, nullable=True))
    op.add_column("bookings", sa.Column("cancellation_resolved_at", tz, nullable=True))
    op.add_column("bookings", sa.Column("cancellation_resolved_by_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("bookings", sa.Column("cancellation_response", sa.Text, nullable=True))
    op.create_index("ix_bookings_customer_id", "bookings", ["customer_id"])
    op.create_index("ix_bookings_assigned_employee_id", "bookings", ["assigned_employee_id"])
    op.drop_constraint("ck_bookings_status", "bookings", type_="check")
    op.create_check_constraint(
        "ck_bookings_status",
        "bookings",
        "status IN ('pending','confirmed','declined','cancelled','checked_in','completed','no_show')",
    )
    op.create_check_constraint(
        "ck_bookings_cancellation_status",
        "bookings",
        "cancellation_status IS NULL OR cancellation_status IN ('pending','approved','declined')",
    )

    op.create_table(
        "booking_status_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
    )
    op.create_index("ix_booking_status_history_booking_id", "booking_status_history", ["booking_id"])
    op.execute(
        "INSERT INTO booking_status_history (booking_id, from_status, to_status, actor_role, reason, created_at) "
        "SELECT id, NULL, status, 'system', 'Status when history tracking was introduced', "
        "COALESCE(status_changed_at, created_at) FROM bookings"
    )

    op.create_table(
        "activity_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("actor_label", sa.String(160), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("detail", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
    )
    op.create_index("ix_activity_log_actor_id", "activity_log", ["actor_id"])
    op.create_index("ix_activity_log_action", "activity_log", ["action"])
    op.create_index("ix_activity_log_created_at", "activity_log", ["created_at"])

    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
    )
    op.create_index("ix_rate_limit_events_key_created", "rate_limit_events", ["key_hash", "created_at"])

    op.create_table(
        "booking_date_overrides",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False, unique=True),
        sa.Column("is_closed", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("start_time", sa.Time, nullable=True),
        sa.Column("end_time", sa.Time, nullable=True),
        sa.Column("note", sa.String(160), nullable=True),
        sa.CheckConstraint(
            "is_closed OR (start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)",
            name="ck_booking_date_overrides_window",
        ),
    )

    # --- menu ---
    op.add_column("menu_categories", sa.Column("notes", JSONB, nullable=False, server_default="[]"))
    op.add_column("menu_categories", sa.Column("imported_snapshot", JSONB, nullable=True))
    op.add_column("menu_items", sa.Column("slug", sa.String(120), nullable=True))
    op.create_unique_constraint("uq_menu_items_slug", "menu_items", ["slug"])
    op.add_column("menu_items", sa.Column("is_published", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("menu_items", sa.Column("addons", JSONB, nullable=False, server_default="[]"))
    op.add_column("menu_items", sa.Column("source_document", sa.String(120), nullable=True))
    op.add_column("menu_items", sa.Column("source_page", sa.Integer, nullable=True))
    op.add_column("menu_items", sa.Column("review_note", sa.Text, nullable=True))
    op.add_column("menu_items", sa.Column("imported_snapshot", JSONB, nullable=True))
    op.drop_constraint("ck_menu_items_source", "menu_items", type_="check")
    op.create_check_constraint(
        "ck_menu_items_source", "menu_items", "source IN ('listing','menu_photo','owner','owner_pdf')"
    )


def downgrade() -> None:
    # Refuses to run if it would lose data that only exists in the new structures.
    conn = op.get_bind()
    blocking = conn.execute(sa.text(
        "SELECT (SELECT count(*) FROM accounts WHERE role <> 'owner') + "
        "(SELECT count(*) FROM bookings WHERE status IN ('checked_in','completed','no_show')) + "
        "(SELECT count(*) FROM menu_items WHERE source = 'owner_pdf')"
    )).scalar()
    if blocking:
        raise RuntimeError(
            "Downgrade would discard customer/employee accounts, newer booking statuses or imported menu items. "
            "Back up and remove them deliberately first."
        )
    op.drop_constraint("ck_menu_items_source", "menu_items", type_="check")
    op.create_check_constraint("ck_menu_items_source", "menu_items", "source IN ('listing','menu_photo','owner')")
    for column in ("imported_snapshot", "review_note", "source_page", "source_document", "addons", "is_published"):
        op.drop_column("menu_items", column)
    op.drop_constraint("uq_menu_items_slug", "menu_items", type_="unique")
    op.drop_column("menu_items", "slug")
    op.drop_column("menu_categories", "imported_snapshot")
    op.drop_column("menu_categories", "notes")
    for table in ("booking_date_overrides", "rate_limit_events", "activity_log", "booking_status_history"):
        op.drop_table(table)
    op.drop_constraint("ck_bookings_cancellation_status", "bookings", type_="check")
    op.drop_constraint("ck_bookings_status", "bookings", type_="check")
    op.create_check_constraint("ck_bookings_status", "bookings", "status IN ('pending','confirmed','declined','cancelled')")
    for column in ("cancellation_response", "cancellation_resolved_by_id", "cancellation_resolved_at",
                   "cancellation_requested_at", "cancellation_reason", "cancellation_status", "updated_at",
                   "version", "assigned_employee_id", "customer_id", "request_hash"):
        op.drop_column("bookings", column)
    for table in ("password_reset_tokens", "account_sessions", "accounts"):
        op.drop_table(table)
