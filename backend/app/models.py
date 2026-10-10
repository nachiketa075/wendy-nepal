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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

BOOKING_STATUSES = ("pending", "confirmed", "declined", "cancelled")
MENU_SOURCES = ("listing", "menu_photo", "owner")


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OwnerSession(Base):
    __tablename__ = "owner_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), index=True)
    # Only a SHA-256 digest of the cookie token is stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))

    owner: Mapped[Owner] = relationship()


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("status IN ('pending','confirmed','declined','cancelled')", name="ck_bookings_status"),
        CheckConstraint("party_size >= 1", name="ck_bookings_party_size"),
        Index("ix_bookings_status_requested_at", "status", "requested_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(16), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
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
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status_changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


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
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


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


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    tagline: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category", order_by="MenuItem.sort_order, MenuItem.id"
    )


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("source IN ('listing','menu_photo','owner')", name="ck_menu_items_source"),
        CheckConstraint("price_npr IS NULL OR price_npr >= 0", name="ck_menu_items_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("menu_categories.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Only ever set by the owner; a value here is treated as a confirmed price.
    price_npr: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # Where the item came from: a public listing, a guest photo of the menu
    # board, or the owner themselves.
    source: Mapped[str] = mapped_column(String(16), default="owner", server_default="owner")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    category: Mapped[MenuCategory] = relationship(back_populates="items")
