import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

ROLES = ("owner", "employee", "customer")
MENU_SOURCES = ("listing", "menu_photo", "owner", "owner_pdf")

_now = func.now()


class Account(Base):
    """One table for every sign-in: owner, employee and customer.

    The role is set by the server when the account is created (public
    registration always creates a customer) and is never taken from a request.
    """

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("role IN ('owner','employee','customer')", name="ck_accounts_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-case
    # NULL until an invited employee sets a password through their setup link.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Employee permissions (list of keys from app.permissions). Empty by default.
    permissions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now)

    def can(self, permission: str) -> bool:
        if not self.is_active:
            return False
        if self.role == "owner":
            return True
        return self.role == "employee" and permission in (self.permissions or [])


class AccountSession(Base):
    __tablename__ = "account_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    # Only a SHA-256 digest of the cookie token is stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship()


class PasswordResetToken(Base):
    """Single-use token for password reset and for an invited employee's first password."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(16), default="reset", server_default="reset")  # reset | setup
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','declined','cancelled','checked_in','completed','no_show')",
            name="ck_bookings_status",
        ),
        CheckConstraint("party_size >= 1", name="ck_bookings_party_size"),
        Index("ix_bookings_status_requested_at", "status", "requested_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(16), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Digest of the request body, so a reused idempotency key with different data is caught.
    request_hash: Mapped[str | None] = mapped_column(String(64))
    # NULL for guest requests. Never filled in by matching phone or email.
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    assigned_employee_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))  # E.164
    email: Mapped[str | None] = mapped_column(String(254))
    # Date and time as the guest asked for them, in the business timezone.
    requested_date: Mapped[dt.date] = mapped_column(Date, index=True)
    requested_time: Mapped[dt.time] = mapped_column(Time)
    requested_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    party_size: Mapped[int] = mapped_column(Integer)
    special_requests: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    internal_notes: Mapped[str | None] = mapped_column(Text)
    # Incremented on every change; staff send the version they saw so two people
    # cannot silently overwrite each other.
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now, onupdate=_now)
    status_changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    # Customer's request to cancel, resolved by staff.
    cancellation_status: Mapped[str | None] = mapped_column(String(16))  # pending | approved | declined
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    cancellation_requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    cancellation_response: Mapped[str | None] = mapped_column(Text)  # shown to the customer

    assigned_employee: Mapped[Account | None] = relationship(foreign_keys=[assigned_employee_id])
    history: Mapped[list["BookingStatusHistory"]] = relationship(
        back_populates="booking", order_by="BookingStatusHistory.id", cascade="all, delete-orphan"
    )


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    actor_role: Mapped[str] = mapped_column(String(16))  # owner | employee | customer | guest | system
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now)

    booking: Mapped[Booking] = relationship(back_populates="history")
    actor: Mapped[Account | None] = relationship()


class ActivityLog(Base):
    """Who did what, for the owner to review. Never exposed to customers."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    actor_role: Mapped[str] = mapped_column(String(16))
    actor_label: Mapped[str] = mapped_column(String(160))  # name at the time, kept if the account goes
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now, index=True)


class RateLimitEvent(Base):
    """Shared rate-limit counter, so limits hold across API workers."""

    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("ix_rate_limit_events_key_created", "key_hash", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now)


class BookingSettings(Base):
    """Single-row table (id = 1) holding owner-configurable booking rules."""

    __tablename__ = "booking_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_booking_settings_singleton"),
        CheckConstraint("min_party_size >= 1 AND max_party_size >= min_party_size", name="ck_booking_settings_party"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # False until the owner reviews the provisional demo values.
    owner_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    min_party_size: Mapped[int] = mapped_column(Integer)
    max_party_size: Mapped[int] = mapped_column(Integer)
    min_lead_minutes: Mapped[int] = mapped_column(Integer)
    max_advance_days: Mapped[int] = mapped_column(Integer)
    slot_interval_minutes: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=_now, onupdate=_now)


class BookingWindow(Base):
    __tablename__ = "booking_windows"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_booking_windows_weekday"),
        CheckConstraint("start_time < end_time", name="ck_booking_windows_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int] = mapped_column(SmallInteger, index=True)  # 0 = Monday
    start_time: Mapped[dt.time] = mapped_column(Time)
    end_time: Mapped[dt.time] = mapped_column(Time)  # last time a guest may request


class BookingDateOverride(Base):
    """A closed date, or a date with its own booking window instead of the weekday's."""

    __tablename__ = "booking_date_overrides"
    __table_args__ = (
        CheckConstraint(
            "is_closed OR (start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)",
            name="ck_booking_date_overrides_window",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, unique=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    start_time: Mapped[dt.time | None] = mapped_column(Time)
    end_time: Mapped[dt.time | None] = mapped_column(Time)
    note: Mapped[str | None] = mapped_column(String(160))  # internal


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    tagline: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Section-wide extras, e.g. [{"label": "Extra Cheese Topping", "price": 70, "prefix": "+"}]
    notes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # What the last menu import wrote; NULL for categories the owner created.
    # If the live values differ from this, the owner has edited them since.
    imported_snapshot: Mapped[dict | None] = mapped_column(JSONB)

    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category", order_by="MenuItem.sort_order, MenuItem.id"
    )


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("source IN ('listing','menu_photo','owner','owner_pdf')", name="ck_menu_items_source"),
        CheckConstraint("price_npr IS NULL OR price_npr >= 0", name="ck_menu_items_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("menu_categories.id", ondelete="RESTRICT"), index=True)
    # Stable identifier from the import file ("brunch-vegan-porridge"); NULL for owner-created items.
    slug: Mapped[str | None] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Hidden items stay in the owner's editor but are not on the public menu.
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    price_npr: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # [{"label": "add on 2 eggs", "price": 80, "unit": "per piece"}]
    addons: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    source: Mapped[str] = mapped_column(String(16), default="owner", server_default="owner")
    source_document: Mapped[str | None] = mapped_column(String(120))
    source_page: Mapped[int | None] = mapped_column(Integer)
    review_note: Mapped[str | None] = mapped_column(Text)  # question for the owner; internal
    imported_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    category: Mapped[MenuCategory] = relationship(back_populates="items")
