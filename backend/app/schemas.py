import datetime as dt
import re
from decimal import Decimal
from typing import Annotated, Literal

import phonenumbers
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
    model_validator,
)

Stripped = Annotated[str, StringConstraints(strip_whitespace=True)]
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _blank_to_none(value):
    if isinstance(value, str) and not value.strip():
        return None
    return value


class StrictModel(BaseModel):
    # Unknown fields (for example a client-supplied "status") are rejected.
    model_config = ConfigDict(extra="forbid")


# ---------- Bookings ----------


class BookingCreate(StrictModel):
    full_name: Annotated[Stripped, Field(min_length=2, max_length=120)]
    phone: Annotated[Stripped, Field(min_length=6, max_length=32)]
    email: EmailStr | None = None
    requested_date: dt.date
    requested_time: dt.time
    party_size: Annotated[int, Field(ge=1, le=500)]
    special_requests: Annotated[Stripped, Field(max_length=1000)] | None = None
    idempotency_key: Annotated[str, Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")] | None = None

    _blank_email = field_validator("email", "special_requests", mode="before")(_blank_to_none)

    @field_validator("full_name", "special_requests")
    @classmethod
    def _no_control_chars(cls, value: str | None) -> str | None:
        if value and _CONTROL_CHARS.search(value):
            raise ValueError("Contains characters that are not allowed.")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return _normalise_phone(value)

    @field_validator("requested_time")
    @classmethod
    def _plain_time(cls, value: dt.time) -> dt.time:
        if value.tzinfo is not None:
            raise ValueError("Send the time without a timezone; it is read as Pokhara time.")
        return value.replace(second=0, microsecond=0)


class BookingReceipt(BaseModel):
    reference: str
    status: Literal["pending"]
    message: str


class CancellationOut(BaseModel):
    status: Literal["pending", "approved", "declined"]
    reason: str | None
    requested_at: dt.datetime | None
    resolved_at: dt.datetime | None
    response: str | None


class CustomerBookingOut(BaseModel):
    """What a customer sees of their own booking. No internal notes, staff or audit data."""

    reference: str
    status: str
    full_name: str
    phone: str
    email: str | None
    requested_date: dt.date
    requested_time: dt.time
    party_size: int
    special_requests: str | None
    created_at: dt.datetime
    status_changed_at: dt.datetime | None
    cancellation: CancellationOut | None
    can_request_cancellation: bool


class CustomerBookingList(BaseModel):
    items: list[CustomerBookingOut]
    total: int
    limit: int
    offset: int


class CancellationRequestIn(StrictModel):
    reason: Annotated[Stripped, Field(max_length=500)] | None = None

    _blank = field_validator("reason", mode="before")(_blank_to_none)


class PersonRef(BaseModel):
    id: int
    full_name: str


class HistoryEntry(BaseModel):
    from_status: str | None
    to_status: str
    actor: str
    actor_role: str
    reason: str | None
    created_at: dt.datetime


class StaffBookingOut(BaseModel):
    id: int
    reference: str
    full_name: str
    # phone and email are omitted (null) unless the viewer may see contact details.
    contact_visible: bool
    phone: str | None
    email: str | None
    requested_date: dt.date
    requested_time: dt.time
    party_size: int
    special_requests: str | None
    status: str
    internal_notes: str | None
    version: int
    has_account: bool
    created_at: dt.datetime
    status_changed_at: dt.datetime | None
    assigned_employee: PersonRef | None
    cancellation: CancellationOut | None
    # Status changes this viewer may make right now, decided by the server.
    allowed_statuses: list[str]
    can_edit_notes: bool
    can_resolve_cancellation: bool
    history: list[HistoryEntry] | None = None


class StaffBookingList(BaseModel):
    items: list[StaffBookingOut]
    total: int
    limit: int
    offset: int
    counts: dict[str, int]
    scope: Literal["all", "assigned"]


class StaffAlerts(BaseModel):
    pending_count: int
    newest_pending_id: int | None
    cancellation_requests: int


class StaffStatusChange(StrictModel):
    status: Literal["confirmed", "declined", "cancelled", "checked_in", "completed", "no_show"]
    version: Annotated[int, Field(ge=1)]
    reason: Annotated[Stripped, Field(max_length=500)] | None = None

    _blank = field_validator("reason", mode="before")(_blank_to_none)


class StaffNotes(StrictModel):
    internal_notes: Annotated[Stripped, Field(max_length=2000)] | None = None
    version: Annotated[int, Field(ge=1)]

    _blank = field_validator("internal_notes", mode="before")(_blank_to_none)


class AssignIn(StrictModel):
    employee_id: int | None
    version: Annotated[int, Field(ge=1)]


class CancellationDecision(StrictModel):
    decision: Literal["approve", "decline"]
    version: Annotated[int, Field(ge=1)]
    response: Annotated[Stripped, Field(max_length=500)] | None = None

    _blank = field_validator("response", mode="before")(_blank_to_none)


# ---------- Booking settings ----------


def _plain(value: dt.time) -> dt.time:
    return value.replace(second=0, microsecond=0, tzinfo=None)


class WindowIn(StrictModel):
    weekday: Annotated[int, Field(ge=0, le=6)]
    start_time: dt.time
    end_time: dt.time

    @model_validator(mode="after")
    def _order(self) -> "WindowIn":
        self.start_time, self.end_time = _plain(self.start_time), _plain(self.end_time)
        if self.start_time >= self.end_time:
            raise ValueError("Each booking window must start before it ends.")
        return self


class OverrideIn(StrictModel):
    date: dt.date
    is_closed: bool
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    note: Annotated[Stripped, Field(max_length=160)] | None = None

    _blank = field_validator("note", "start_time", "end_time", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def _window(self) -> "OverrideIn":
        if self.is_closed:
            self.start_time = self.end_time = None
            return self
        if self.start_time is None or self.end_time is None:
            raise ValueError("A special day needs a start and end time, or mark it closed.")
        self.start_time, self.end_time = _plain(self.start_time), _plain(self.end_time)
        if self.start_time >= self.end_time:
            raise ValueError("A special day's window must start before it ends.")
        return self


class SettingsIn(StrictModel):
    booking_enabled: bool
    owner_confirmed: bool
    min_party_size: Annotated[int, Field(ge=1, le=100)]
    max_party_size: Annotated[int, Field(ge=1, le=100)]
    min_lead_minutes: Annotated[int, Field(ge=0, le=7 * 24 * 60)]
    max_advance_days: Annotated[int, Field(ge=1, le=365)]
    slot_interval_minutes: Literal[15, 30, 60]
    windows: Annotated[list[WindowIn], Field(max_length=28)]
    overrides: Annotated[list[OverrideIn], Field(max_length=120)] = []

    @model_validator(mode="after")
    def _consistent(self) -> "SettingsIn":
        if self.min_party_size > self.max_party_size:
            raise ValueError("Smallest party size cannot be larger than the largest.")
        by_day: dict[int, list[WindowIn]] = {}
        for window in self.windows:
            by_day.setdefault(window.weekday, []).append(window)
        for windows in by_day.values():
            windows.sort(key=lambda w: w.start_time)
            for earlier, later in zip(windows, windows[1:]):
                if later.start_time <= earlier.end_time:
                    raise ValueError("Booking windows on the same day cannot overlap.")
        dates = [o.date for o in self.overrides]
        if len(dates) != len(set(dates)):
            raise ValueError("Each closed or special date can only be listed once.")
        return self


class WindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekday: int
    start_time: dt.time
    end_time: dt.time


class OverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: dt.date
    is_closed: bool
    start_time: dt.time | None
    end_time: dt.time | None
    note: str | None = None


class PublicOverride(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: dt.date
    is_closed: bool
    start_time: dt.time | None
    end_time: dt.time | None


class SettingsOut(BaseModel):
    booking_enabled: bool
    owner_confirmed: bool
    min_party_size: int
    max_party_size: int
    min_lead_minutes: int
    max_advance_days: int
    slot_interval_minutes: int
    windows: list[WindowOut]
    overrides: list[OverrideOut]


class PublicBookingConfig(BaseModel):
    accepting_requests: bool
    timezone: str
    today: dt.date
    min_party_size: int
    max_party_size: int
    min_lead_minutes: int
    max_advance_days: int
    slot_interval_minutes: int
    windows: list[WindowOut]
    overrides: list[PublicOverride]


# ---------- Menu ----------

Price = Annotated[Decimal, Field(ge=0, le=1_000_000, decimal_places=2)]


class Addon(StrictModel):
    label: Annotated[Stripped, Field(min_length=1, max_length=120)]
    price: Price
    unit: Annotated[Stripped, Field(max_length=40)] | None = None
    prefix: Annotated[Stripped, Field(max_length=4)] | None = None

    _blank = field_validator("unit", "prefix", mode="before")(_blank_to_none)


Addons = Annotated[list[Addon], Field(max_length=12)]


class PublicMenuItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str | None
    category_id: int
    name: str
    description: str | None
    is_available: bool
    price_npr: Decimal | None
    addons: list[dict]
    sort_order: int


class PublicMenuCategory(BaseModel):
    id: int
    slug: str
    name: str
    tagline: str | None
    sort_order: int
    notes: list[dict]
    items: list[PublicMenuItem]


class PublicMenu(BaseModel):
    categories: list[PublicMenuCategory]


class MenuItemOut(PublicMenuItem):
    is_published: bool
    source: str
    source_document: str | None
    source_page: int | None
    review_note: str | None
    edited_since_import: bool


class MenuCategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    tagline: str | None
    sort_order: int
    notes: list[dict]
    items: list[MenuItemOut]


class MenuOut(BaseModel):
    categories: list[MenuCategoryOut]


class MenuItemCreate(StrictModel):
    category_id: int
    name: Annotated[Stripped, Field(min_length=1, max_length=120)]
    description: Annotated[Stripped, Field(max_length=600)] | None = None
    is_available: bool = True
    is_published: bool = True
    price_npr: Price | None = None
    addons: Addons = []
    sort_order: int = 0

    _blank = field_validator("description", "price_npr", mode="before")(_blank_to_none)


class MenuItemUpdate(StrictModel):
    category_id: int | None = None
    name: Annotated[Stripped, Field(min_length=1, max_length=120)] | None = None
    description: Annotated[Stripped, Field(max_length=600)] | None = None
    is_available: bool | None = None
    is_published: bool | None = None
    price_npr: Price | None = None
    addons: Addons | None = None
    sort_order: int | None = None

    _blank = field_validator("description", "price_npr", mode="before")(_blank_to_none)


class MenuCategoryCreate(StrictModel):
    name: Annotated[Stripped, Field(min_length=1, max_length=80)]
    tagline: Annotated[Stripped, Field(max_length=80)] | None = None
    notes: Addons = []
    sort_order: int = 0

    _blank = field_validator("tagline", mode="before")(_blank_to_none)


class MenuCategoryUpdate(StrictModel):
    name: Annotated[Stripped, Field(min_length=1, max_length=80)] | None = None
    tagline: Annotated[Stripped, Field(max_length=80)] | None = None
    notes: Addons | None = None
    sort_order: int | None = None

    _blank = field_validator("tagline", mode="before")(_blank_to_none)


# ---------- Accounts ----------

Password = Annotated[str, Field(min_length=12, max_length=256)]
PermissionKey = Literal[
    "bookings.view_assigned", "bookings.view_all", "bookings.view_contact", "bookings.approve",
    "bookings.decline", "bookings.cancel", "bookings.check_in", "bookings.complete",
    "bookings.mark_no_show", "bookings.edit_notes", "menu.manage", "booking_settings.manage",
    "inventory.view", "inventory.manage_items", "inventory.adjust_stock",
]


def _normalise_phone(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith("+"):
        raise ValueError("Include your country code, for example +977.")
    try:
        parsed = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException:
        raise ValueError("Enter a valid phone number with country code.") from None
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Enter a valid phone number with country code.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class LoginIn(StrictModel):
    email: Annotated[Stripped, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=256)]
    # Which sign-in page was used. It can only narrow who may sign in there;
    # the role itself always comes from the account.
    portal: Literal["customer", "owner", "employee"] | None = None


class RegisterIn(StrictModel):
    """Public registration. There is deliberately no role or permissions field:
    extra fields are rejected and the server always creates a customer."""

    full_name: Annotated[Stripped, Field(min_length=2, max_length=120)]
    email: EmailStr
    password: Password
    phone: Annotated[Stripped, Field(max_length=32)] | None = None

    _blank = field_validator("phone", mode="before")(_blank_to_none)
    _phone = field_validator("phone")(_normalise_phone)

    @field_validator("full_name")
    @classmethod
    def _clean(cls, value: str) -> str:
        if _CONTROL_CHARS.search(value):
            raise ValueError("Contains characters that are not allowed.")
        return value


class AccountOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    role: Literal["owner", "employee", "customer"]
    permissions: list[str]
    csrf_token: str


class ProfileUpdate(StrictModel):
    full_name: Annotated[Stripped, Field(min_length=2, max_length=120)] | None = None
    phone: Annotated[Stripped, Field(max_length=32)] | None = None

    _blank = field_validator("phone", mode="before")(_blank_to_none)
    _phone = field_validator("phone")(_normalise_phone)


class PasswordChange(StrictModel):
    current_password: Annotated[str, Field(min_length=1, max_length=256)]
    new_password: Password


class ResetRequest(StrictModel):
    email: Annotated[Stripped, Field(min_length=3, max_length=254)]


class ResetConfirm(StrictModel):
    token: Annotated[str, Field(min_length=20, max_length=200)]
    new_password: Password


class AuthConfig(BaseModel):
    password_reset_by_email: bool
    min_password_length: int


class EmployeeCreate(StrictModel):
    email: EmailStr
    full_name: Annotated[Stripped, Field(min_length=2, max_length=120)]
    permissions: list[PermissionKey] = []


class EmployeeUpdate(StrictModel):
    full_name: Annotated[Stripped, Field(min_length=2, max_length=120)] | None = None
    permissions: list[PermissionKey] | None = None
    is_active: bool | None = None


class EmployeeOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    permissions: list[str]
    has_password: bool
    active_sessions: int
    created_at: dt.datetime


class EmployeeCreated(BaseModel):
    employee: EmployeeOut
    # One-time link for the employee to choose their password. Shown once.
    setup_url: str
    setup_expires_at: dt.datetime


class ActivityEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_label: str
    actor_role: str
    action: str
    target_type: str | None
    target_id: str | None
    detail: dict
    created_at: dt.datetime


class ActivityList(BaseModel):
    items: list[ActivityEntry]
    total: int


# ---------- Inventory (staff only) ----------

InventoryCategory = Literal["fruit_veg", "dairy", "coffee_tea", "dry_goods", "packaging", "cleaning", "other"]
InventoryUnit = Literal["kg", "litre", "piece"]
IdempotencyKey = Annotated[str, Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
MAX_QUANTITY = Decimal("999999999.999")


def _parse_quantity(value):
    """Exact decimal from a JSON string or number. Floats go through their
    shortest text form, so 0.1 stays 0.1. At most 3 decimal places."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Enter a number.")
    try:
        number = Decimal(str(value).strip())
    except ArithmeticError:
        raise ValueError("Enter a number, for example 2.5.") from None
    if not number.is_finite():
        raise ValueError("Enter a number, for example 2.5.")
    if number.as_tuple().exponent < -3 and number != number.quantize(Decimal("0.001")):
        raise ValueError("Use at most 3 decimal places.")
    if number < 0:
        raise ValueError("Cannot be negative.")
    if number > MAX_QUANTITY:
        raise ValueError("That number is too large.")
    return number.quantize(Decimal("0.001"))


def _format_quantity(value: Decimal) -> str:
    """2.500 -> "2.5", 100.000 -> "100"; never exponent notation."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


QuantityOut = Annotated[Decimal, PlainSerializer(_format_quantity, return_type=str)]


def _clean_name(value: str) -> str:
    if _CONTROL_CHARS.search(value):
        raise ValueError("Contains characters that are not allowed.")
    return " ".join(value.split())


class InventoryItemCreate(StrictModel):
    name: Annotated[Stripped, Field(min_length=1, max_length=120)]
    category: InventoryCategory
    unit: InventoryUnit
    low_stock_threshold: Decimal | None = None
    # Stock already on the shelf. Recorded as an "opening" movement, not set silently.
    opening_quantity: Decimal | None = None
    idempotency_key: IdempotencyKey

    _quantities = field_validator("low_stock_threshold", "opening_quantity", mode="before")(_parse_quantity)
    _name = field_validator("name")(_clean_name)


class InventoryItemUpdate(StrictModel):
    """Item details only. There is deliberately no quantity field: stock changes
    only through a recorded movement."""

    version: int
    name: Annotated[Stripped, Field(min_length=1, max_length=120)] | None = None
    category: InventoryCategory | None = None
    unit: InventoryUnit | None = None
    low_stock_threshold: Decimal | None = None  # null clears it
    is_active: bool | None = None  # false archives the item

    _threshold = field_validator("low_stock_threshold", mode="before")(_parse_quantity)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return _clean_name(value) if value is not None else None


class InventoryMovementIn(StrictModel):
    kind: Literal["stock_in", "stock_out", "adjustment"]
    # stock_in / stock_out: the amount received or used (more than 0).
    # adjustment: the quantity actually counted, which becomes the new stock.
    quantity: Decimal
    reason: Annotated[Stripped, Field(max_length=300)] | None = None
    # Required for an adjustment: the item version the count was made against.
    version: int | None = None
    idempotency_key: IdempotencyKey

    _quantity = field_validator("quantity", mode="before")(_parse_quantity)
    _blank_reason = field_validator("reason", mode="before")(_blank_to_none)

    @field_validator("reason")
    @classmethod
    def _plain_reason(cls, value: str | None) -> str | None:
        if value and _CONTROL_CHARS.search(value):
            raise ValueError("Contains characters that are not allowed.")
        return value


class InventoryItemOut(BaseModel):
    id: int
    name: str
    category: str
    unit: str
    quantity: QuantityOut
    low_stock_threshold: QuantityOut | None
    is_low: bool
    is_active: bool
    version: int
    # Once true, the unit can no longer be changed.
    has_movements: bool
    created_at: dt.datetime
    updated_at: dt.datetime


class InventoryItemList(BaseModel):
    items: list[InventoryItemOut]
    total: int
    limit: int
    offset: int
    # Active items at or below their threshold, regardless of the filters.
    low_stock_count: int


class InventoryMovementOut(BaseModel):
    id: int
    item_id: int
    item_name: str
    unit: str
    kind: str
    quantity_change: QuantityOut
    balance_after: QuantityOut
    reason: str | None
    actor_name: str
    actor_role: str
    created_at: dt.datetime


class InventoryMovementList(BaseModel):
    items: list[InventoryMovementOut]
    total: int
    limit: int
    offset: int


class InventoryMovementResult(BaseModel):
    item: InventoryItemOut
    movement: InventoryMovementOut
