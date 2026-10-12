// FICTIONAL data for the development-only UI preview. None of these people,
// phone numbers or bookings are real, and nothing here comes from the database.
// Phone numbers use obviously fake digits; emails use the reserved example.com domain.
const day = (offset) => {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toISOString().slice(0, 10)
}

export const PREVIEW_CUSTOMER = { name: 'Sample Customer', email: 'sample.customer@example.com' }
export const PREVIEW_EMPLOYEE = { name: 'Sample Employee', email: 'sample.employee@example.com' }

export const PREVIEW_BOOKINGS = [
  { id: 'p1', reference: 'DEMO-0001', full_name: 'Sample Guest One', phone: '+977 9800000001', email: 'guest.one@example.com', requested_date: day(1), requested_time: '09:30', party_size: 2, special_requests: 'Window seat if possible', status: 'pending' },
  { id: 'p2', reference: 'DEMO-0002', full_name: 'Sample Guest Two', phone: '+977 9800000002', email: null, requested_date: day(1), requested_time: '11:00', party_size: 6, special_requests: null, status: 'confirmed' },
  { id: 'p3', reference: 'DEMO-0003', full_name: 'Sample Guest Three', phone: '+91 9000000003', email: 'guest.three@example.com', requested_date: day(3), requested_time: '08:00', party_size: 4, special_requests: 'One high chair', status: 'pending' },
  { id: 'p4', reference: 'DEMO-0004', full_name: 'Sample Guest Four', phone: '+44 7000000004', email: null, requested_date: day(0), requested_time: '16:00', party_size: 3, special_requests: null, status: 'confirmed' },
  { id: 'p5', reference: 'DEMO-0005', full_name: 'Sample Guest Five', phone: '+977 9800000005', email: null, requested_date: day(-4), requested_time: '10:00', party_size: 2, special_requests: null, status: 'declined' },
  { id: 'p6', reference: 'DEMO-0006', full_name: 'Sample Guest Six', phone: '+977 9800000006', email: 'guest.six@example.com', requested_date: day(-9), requested_time: '12:30', party_size: 5, special_requests: 'Birthday', status: 'cancelled' },
]

// What one signed-in customer would see: only their own bookings.
export const PREVIEW_CUSTOMER_BOOKINGS = [
  { ...PREVIEW_BOOKINGS[0], full_name: PREVIEW_CUSTOMER.name },
  { ...PREVIEW_BOOKINGS[1], full_name: PREVIEW_CUSTOMER.name, requested_date: day(6) },
  { ...PREVIEW_BOOKINGS[4], full_name: PREVIEW_CUSTOMER.name },
  { ...PREVIEW_BOOKINGS[5], full_name: PREVIEW_CUSTOMER.name, status: 'confirmed', requested_date: day(-20) },
]

export const PREVIEW_EMPLOYEES = [
  { id: 'e1', name: 'Sample Employee A', email: 'employee.a@example.com', active: true, permissions: ['view_bookings', 'view_contact', 'approve_decline', 'check_in'] },
  { id: 'e2', name: 'Sample Employee B', email: 'employee.b@example.com', active: true, permissions: ['view_bookings', 'check_in'] },
  { id: 'e3', name: 'Sample Employee C', email: 'employee.c@example.com', active: false, permissions: [] },
]
