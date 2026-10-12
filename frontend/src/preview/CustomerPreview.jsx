import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AreaShell } from '../auth/AuthLayout.jsx'
import { BUSINESS } from '../lib/business.js'
import { formatDate, formatTime, nowInBusinessTz } from '../lib/time.js'
import { PREVIEW_CUSTOMER, PREVIEW_CUSTOMER_BOOKINGS } from './fixtures.js'
import PreviewBanner, { StatusBadge } from './PreviewBanner.jsx'

const STATES = [
  ['bookings', 'With bookings'],
  ['empty', 'No bookings'],
  ['loading', 'Loading'],
  ['error', 'Error'],
  ['signed-out', 'Signed out'],
]

/** Design preview of the customer area. Fictional data, in memory only, no API calls. */
export default function CustomerPreview() {
  const [view, setView] = useState('bookings')
  const [bookings, setBookings] = useState(PREVIEW_CUSTOMER_BOOKINGS)
  const [openId, setOpenId] = useState(null)
  const [asking, setAsking] = useState(null)

  const today = nowInBusinessTz().date
  const upcoming = bookings.filter((b) => b.requested_date >= today && ['pending', 'confirmed'].includes(b.status))
  const past = bookings.filter((b) => !upcoming.includes(b))

  const requestCancellation = (id) => {
    setBookings((list) => list.map((b) => (b.id === id ? { ...b, cancellationRequested: true } : b)))
    setAsking(null)
  }

  const renderCard = (booking) => {
    const open = openId === booking.id
    const canAsk = upcoming.includes(booking) && !booking.cancellationRequested
    return (
      <li key={booking.id} className="rounded-[5px] border border-line bg-white/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-[24px] tracking-[-0.6px]">
              {formatDate(booking.requested_date)}, {formatTime(booking.requested_time)}
            </h3>
            <p className="text-sm opacity-75">
              {booking.party_size} {booking.party_size === 1 ? 'guest' : 'guests'} · {booking.reference}
            </p>
          </div>
          <StatusBadge status={booking.status} />
        </div>
        {booking.status === 'pending' && <p className="mt-3 text-sm">Not confirmed yet. The team will contact you after checking availability.</p>}
        {booking.cancellationRequested && (
          <p role="status" className="mt-3 rounded-lg bg-citrus/50 p-3 text-sm">
            Cancellation requested. <strong>Preview only:</strong> nothing was sent to the shop.
          </p>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button type="button" className="textlink" aria-expanded={open} onClick={() => setOpenId(open ? null : booking.id)}>
            {open ? 'Hide details' : 'View details'}
          </button>
          {canAsk && asking !== booking.id && (
            <button type="button" className="textlink" onClick={() => setAsking(booking.id)}>
              Ask to cancel
            </button>
          )}
        </div>
        {asking === booking.id && (
          <div className="mt-4 rounded-lg border border-forest/25 p-4 text-sm">
            <p className="mb-3">Ask the shop to cancel this booking? In the finished site the team would confirm the cancellation.</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="pill pill-dark !py-2" onClick={() => requestCancellation(booking.id)}>
                Yes, ask to cancel
              </button>
              <button type="button" className="pill !py-2" onClick={() => setAsking(null)}>
                Keep it
              </button>
            </div>
          </div>
        )}
        {open && (
          <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-5 gap-y-1.5 border-t border-line pt-4 text-sm">
            <dt className="opacity-65">Name</dt>
            <dd>{booking.full_name}</dd>
            <dt className="opacity-65">Phone</dt>
            <dd>{booking.phone}</dd>
            <dt className="opacity-65">Requests</dt>
            <dd>{booking.special_requests || 'None'}</dd>
            <dt className="opacity-65">Time zone</dt>
            <dd>Pokhara time</dd>
          </dl>
        )}
      </li>
    )
  }

  return (
    <AreaShell
      tagline="MY BOOKINGS"
      title="My bookings (preview)"
      banner={<PreviewBanner />}
      right={view !== 'signed-out' && <span className="hidden sm:inline">{PREVIEW_CUSTOMER.email}</span>}
    >
      <div role="group" aria-label="Preview state" className="mb-8 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-[1.5px]">Show state:</span>
        {STATES.map(([id, label]) => (
          <button key={id} type="button" className="chip" aria-pressed={view === id} onClick={() => setView(id)}>
            {label}
          </button>
        ))}
      </div>

      {view === 'signed-out' && (
        <div className="max-w-md rounded-[5px] bg-sage p-8">
          <h1 className="mb-3 text-[36px]">You’re signed out.</h1>
          <p className="mb-5 text-sm">Sign in to see your bookings.</p>
          <Link className="pill pill-dark" to="/customer/login">
            Go to sign-in
          </Link>
        </div>
      )}
      {view === 'loading' && <p role="status">Loading your bookings…</p>}
      {view === 'error' && (
        <div role="alert" className="max-w-xl rounded-lg border border-berry/40 bg-berry/5 p-5 text-sm text-berry">
          <p className="font-semibold">We couldn’t load your bookings.</p>
          <p className="mt-1">Please try again. If it keeps happening, call {BUSINESS.phoneDisplay}.</p>
          <button type="button" className="pill mt-4 !py-2 text-forest" onClick={() => setView('bookings')}>
            Try again
          </button>
        </div>
      )}
      {view === 'empty' && (
        <div className="max-w-xl rounded-[5px] bg-sage p-8">
          <h1 className="mb-3 text-[36px]">No bookings yet.</h1>
          <p className="mb-5 text-sm">When you ask for a table, it will show up here with its status.</p>
          <a className="pill pill-dark" href="/#book">
            Request a table
          </a>
        </div>
      )}
      {view === 'bookings' && (
        <>
          <h1 className="mb-6 text-[40px]">My bookings</h1>
          <section aria-labelledby="upcoming-title" className="mb-10">
            <h2 id="upcoming-title" className="mb-4 text-[28px] tracking-[-0.6px]">
              Upcoming
            </h2>
            {upcoming.length ? (
              <ul className="grid gap-4 lg:grid-cols-2">
                {upcoming.map(renderCard)}
              </ul>
            ) : (
              <p className="text-sm">Nothing coming up.</p>
            )}
          </section>
          <section aria-labelledby="past-title">
            <h2 id="past-title" className="mb-4 text-[28px] tracking-[-0.6px]">
              Past
            </h2>
            <ul className="grid gap-4 lg:grid-cols-2">
              {past.map(renderCard)}
            </ul>
          </section>
        </>
      )}
    </AreaShell>
  )
}
