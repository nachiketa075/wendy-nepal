"""Staff-only inventory: items and an append-only stock movement history.

Additive only. No existing table or row is changed:

* Two new tables, `inventory_items` and `inventory_movements`. They start empty;
  no stock quantities are seeded and no menu items are copied into them.
* Employees' permissions are not touched, so nobody gains inventory access
  until the owner grants it.
* A trigger refuses UPDATE and DELETE on `inventory_movements`, so recorded
  stock history cannot be rewritten, even by a bug in the application. The one
  change it allows is the database clearing `actor_id` when an account is
  deleted (for example under the retention policy); the actor's name stays.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_now = sa.text("now()")
tz = sa.DateTime(timezone=True)
quantity = sa.Numeric(12, 3)


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("quantity", quantity, nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", quantity, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
        sa.Column("updated_at", tz, nullable=False, server_default=_now),
        sa.CheckConstraint("unit IN ('kg','litre','piece')", name="ck_inventory_items_unit"),
        sa.CheckConstraint(
            "category IN ('fruit_veg','dairy','coffee_tea','dry_goods','packaging','cleaning','other')",
            name="ck_inventory_items_category",
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_items_quantity"),
        sa.CheckConstraint("low_stock_threshold IS NULL OR low_stock_threshold >= 0", name="ck_inventory_items_threshold"),
        sa.CheckConstraint(
            "unit <> 'piece' OR (quantity = trunc(quantity) AND "
            "(low_stock_threshold IS NULL OR low_stock_threshold = trunc(low_stock_threshold)))",
            name="ck_inventory_items_whole_pieces",
        ),
    )
    op.create_index("uq_inventory_items_name", "inventory_items", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("quantity_change", quantity, nullable=False),
        sa.Column("balance_after", quantity, nullable=False),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("actor_name", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", tz, nullable=False, server_default=_now),
        sa.CheckConstraint("kind IN ('opening','stock_in','stock_out','adjustment')", name="ck_inventory_movements_kind"),
        sa.CheckConstraint("balance_after >= 0", name="ck_inventory_movements_balance"),
        sa.CheckConstraint(
            "(kind IN ('opening','stock_in') AND quantity_change > 0) OR "
            "(kind = 'stock_out' AND quantity_change < 0) OR kind = 'adjustment'",
            name="ck_inventory_movements_sign",
        ),
        sa.CheckConstraint("kind <> 'adjustment' OR reason IS NOT NULL", name="ck_inventory_movements_reason"),
    )
    op.create_index("ix_inventory_movements_item_id_id", "inventory_movements", ["item_id", "id"])
    op.create_index("ix_inventory_movements_actor_id", "inventory_movements", ["actor_id"])
    op.create_index("ix_inventory_movements_created_at", "inventory_movements", ["created_at"])

    op.execute(
        """
        CREATE FUNCTION inventory_movements_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            -- Allowed: ON DELETE SET NULL from accounts, changing nothing else.
            IF TG_OP = 'UPDATE' AND OLD.actor_id IS NOT NULL AND NEW.actor_id IS NULL
               AND (NEW.id, NEW.item_id, NEW.kind, NEW.quantity_change, NEW.balance_after, NEW.reason,
                    NEW.actor_role, NEW.actor_name, NEW.idempotency_key, NEW.request_hash, NEW.created_at)
                   IS NOT DISTINCT FROM
                   (OLD.id, OLD.item_id, OLD.kind, OLD.quantity_change, OLD.balance_after, OLD.reason,
                    OLD.actor_role, OLD.actor_name, OLD.idempotency_key, OLD.request_hash, OLD.created_at)
            THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'inventory_movements is append-only' USING ERRCODE = 'restrict_violation';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER inventory_movements_append_only BEFORE UPDATE OR DELETE ON inventory_movements "
        "FOR EACH ROW EXECUTE FUNCTION inventory_movements_append_only()"
    )


def downgrade() -> None:
    # Refuses to run if it would discard recorded inventory.
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM inventory_items")).scalar()
    if count:
        raise RuntimeError("Downgrade would discard inventory items and their stock history. Back them up and remove them deliberately first.")
    op.execute("DROP TRIGGER inventory_movements_append_only ON inventory_movements")
    op.execute("DROP FUNCTION inventory_movements_append_only()")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_items")
