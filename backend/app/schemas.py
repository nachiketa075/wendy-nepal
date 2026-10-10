import datetime as dt
import re
from decimal import Decimal
from typing import Annotated, Literal

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

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
    def _normalise_phone(cls, value: str) -> str:
        if not value.startswith("+"):
            raise ValueError("Include your country code, for example +977.")
        try:
            parsed = phonenumbers.parse(value, None)
        except phonenumbers.NumberParseException:
            raise ValueError("Enter a valid phone number with country code.") from None
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Enter a valid phone number with country code.")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

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


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    full_name: str
    phone: str
    email: str | None
    requested_date: dt.date
    requested_time: dt.time
    party_size: int
    special_requests: str | None
    status: str
    internal_notes: str | None
    created_at: dt.datetime
    status_changed_at: dt.datetime | None


class BookingList(BaseModel):
    items: list[BookingOut]
    total: int
    counts: dict[str, int]


class BookingStatusChange(StrictModel):
    status: Literal["confirmed", "declined", "cancelled"]


class BookingNotes(StrictModel):
    internal_notes: Annotated[Stripped, Field(max_length=2000)] | None = None

    _blank = field_validator("internal_notes", mode="before")(_blank_to_none)


# ---------- Booking settings ----------


class WindowIn(StrictModel):
    weekday: Annotated[int, Field(ge=0, le=6)]
    start_time: dt.time
    end_time: dt.time

    @model_validator(mode="after")
    def _order(self) -> "WindowIn":
        self.start_time = self.start_time.replace(second=0, microsecond=0, tzinfo=None)
        self.end_time = self.end_time.replace(second=0, microsecond=0, tzinfo=None)
        if self.start_time >= self.end_time:
            raise ValueError("Each booking window must start before it ends.")
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
        return self


class WindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekday: int
    start_time: dt.time
    end_time: dt.time


class SettingsOut(BaseModel):
    booking_enabled: bool
    owner_confirmed: bool
    min_party_size: int
    max_party_size: int
    min_lead_minutes: int
    max_advance_days: int
    slot_interval_minutes: int
    windows: list[WindowOut]


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


# ---------- Menu ----------


class MenuItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    description: str | None
    is_available: bool
    price_npr: Decimal | None
    source: str
    sort_order: int


class MenuCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    tagline: str | None
    sort_order: int
    items: list[MenuItemOut]


class MenuOut(BaseModel):
    categories: list[MenuCategoryOut]


class MenuItemCreate(StrictModel):
    category_id: int
    name: Annotated[Stripped, Field(min_length=1, max_length=120)]
    description: Annotated[Stripped, Field(max_length=600)] | None = None
    is_available: bool = True
    price_npr: Annotated[Decimal, Field(ge=0, le=1_000_000, decimal_places=2)] | None = None
    sort_order: int = 0

    _blank = field_validator("description", "price_npr", mode="before")(_blank_to_none)


class MenuItemUpdate(StrictModel):
    category_id: int | None = None
    name: Annotated[Stripped, Field(min_length=1, max_length=120)] | None = None
    description: Annotated[Stripped, Field(max_length=600)] | None = None
    is_available: bool | None = None
    price_npr: Annotated[Decimal, Field(ge=0, le=1_000_000, decimal_places=2)] | None = None
    sort_order: int | None = None

    _blank = field_validator("description", "price_npr", mode="before")(_blank_to_none)


class MenuCategoryCreate(StrictModel):
    name: Annotated[Stripped, Field(min_length=1, max_length=80)]
    tagline: Annotated[Stripped, Field(max_length=80)] | None = None
    sort_order: int = 0

    _blank = field_validator("tagline", mode="before")(_blank_to_none)


class MenuCategoryUpdate(StrictModel):
    name: Annotated[Stripped, Field(min_length=1, max_length=80)] | None = None
    tagline: Annotated[Stripped, Field(max_length=80)] | None = None
    sort_order: int | None = None

    _blank = field_validator("tagline", mode="before")(_blank_to_none)


# ---------- Auth ----------


class LoginIn(StrictModel):
    email: Annotated[Stripped, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class SessionOut(BaseModel):
    email: str
    csrf_token: str
