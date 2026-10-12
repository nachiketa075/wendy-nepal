"""Employee permissions. The owner grants these per employee; the server checks
them on every request. Owners implicitly hold all of them."""

PERMISSIONS: dict[str, str] = {
    "bookings.view_assigned": "See bookings assigned to them",
    "bookings.view_all": "See all bookings",
    "bookings.view_contact": "See guests' phone numbers and emails",
    "bookings.approve": "Confirm pending requests",
    "bookings.decline": "Decline pending requests",
    "bookings.cancel": "Cancel bookings and resolve cancellation requests",
    "bookings.check_in": "Check guests in",
    "bookings.complete": "Mark a visit as completed",
    "bookings.mark_no_show": "Mark a booking as a no-show",
    "bookings.edit_notes": "Edit internal notes",
    "menu.manage": "Edit the menu",
    "booking_settings.manage": "Edit booking settings",
}

BOOKING_STATUSES = ("pending", "confirmed", "declined", "cancelled", "checked_in", "completed", "no_show")

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "declined", "cancelled"},
    "confirmed": {"checked_in", "cancelled", "no_show"},
    "checked_in": {"completed"},
    "declined": set(),
    "cancelled": set(),
    "completed": set(),
    "no_show": set(),
}

# Permission an employee needs to move a booking INTO each status.
TRANSITION_PERMISSION: dict[str, str] = {
    "confirmed": "bookings.approve",
    "declined": "bookings.decline",
    "cancelled": "bookings.cancel",
    "checked_in": "bookings.check_in",
    "completed": "bookings.complete",
    "no_show": "bookings.mark_no_show",
}
