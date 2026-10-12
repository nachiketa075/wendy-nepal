// The permissions the owner will be able to grant each employee.
// This list is UI-only in this phase. Real enforcement must happen in the
// backend on every request (see docs/API_HANDOFF.md); hiding a button is not security.
export const PERMISSIONS = [
  { key: 'view_bookings', label: 'View bookings', hint: 'See the list of table requests.' },
  { key: 'view_contact', label: 'View contact details', hint: 'See guests’ phone numbers and emails.' },
  { key: 'approve_decline', label: 'Approve or decline', hint: 'Confirm or decline pending requests.' },
  { key: 'cancel', label: 'Cancel bookings', hint: 'Cancel a pending or confirmed booking.' },
  { key: 'check_in', label: 'Check guests in', hint: 'Mark a confirmed booking as arrived.' },
  { key: 'edit_menu', label: 'Edit the menu', hint: 'Change items, prices and availability.' },
  { key: 'edit_settings', label: 'Edit booking settings', hint: 'Change booking windows and group sizes.' },
]

export const PERMISSION_SETS = {
  none: { label: 'No permissions', permissions: [] },
  floor: { label: 'Floor staff', permissions: ['view_bookings', 'check_in'] },
  host: { label: 'Host', permissions: ['view_bookings', 'view_contact', 'approve_decline', 'check_in'] },
  manager: { label: 'Manager', permissions: PERMISSIONS.map((p) => p.key) },
}
