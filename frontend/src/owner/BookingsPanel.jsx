import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { formatDate, formatDateTime, formatTime } from '../lib/time.js'

const STATUSES = ['pending', 'confirmed', 'declined', 'cancelled']
const STATUS_STYLE = {
  pending: 'bg-citrus text-forest',
  confirmed: 'bg-forest text-cream',
  declined: 'bg-berry/10 text-berry',
  cancelled: 'bg-line text-forest',
}
const ACTIONS = {
  pending: [
    ['confirmed', 'Confirm', 'pill pill-dark'],
    ['declined', 'Decline', 'pill'],
    ['cancelled', 'Cancel', 'pill'],
  ],
  confirmed: [['cancelled', 'Cancel booking', 'pill']],
  declined: [],
  cancelled: [],
}
const ACTION_PROMPT = {
  declined: 'Decline this request? This cannot be undone.',
  cancelled: 'Cancel this booking? This cannot be undone.',
}

export default function BookingsPanel({ onAuthError }) {
  const [filters, setFilters] = useState({ status: 'pending', date_from: '', date_to: '' })
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString()
    try {
      setData(await api(`/owner/bookings${query ? `?${query}` : ''}`))
    } catch (err) {
      if (!onAuthError(err)) setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [filters, onAuthError])

  useEffect(() => {
    load()
  }, [load])

  const setFilter = (name, value) => setFilters((f) => ({ ...f, [name]: value }))
  const total = data ? Object.values(data.counts).reduce((a, b) => a + b, 0) : 0

  return (
    <section aria-labelledby="bookings-title">
      <h1 id="bookings-title" className="mb-2 text-[40px]">
        Table requests
      </h1>
      <p className="mb-6 max-w-2xl text-sm opacity-80">
        Guests are told their table is <strong>not confirmed</strong> until you contact them. This dashboard does not track
        table capacity or send messages: check availability yourself, then call or message the guest and record the
        outcome here.
      </p>

      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
          <button type="button" className="chip" aria-pressed={!filters.status} onClick={() => setFilter('status', '')}>
            All{data ? ` (${total})` : ''}
          </button>
          {STATUSES.map((s) => (
            <button key={s} type="button" className="chip capitalize" aria-pressed={filters.status === s} onClick={() => setFilter('status', s)}>
              {s}
              {data ? ` (${data.counts[s]})` : ''}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs font-semibold uppercase tracking-[1.5px]">
            From
            <input type="date" className="field mt-1 !py-2 font-normal normal-case tracking-normal" value={filters.date_from} onChange={(e) => setFilter('date_from', e.target.value)} />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[1.5px]">
            To
            <input type="date" className="field mt-1 !py-2 font-normal normal-case tracking-normal" value={filters.date_to} onChange={(e) => setFilter('date_to', e.target.value)} />
          </label>
          {(filters.date_from || filters.date_to) && (
            <button type="button" className="textlink mb-2" onClick={() => setFilters((f) => ({ ...f, date_from: '', date_to: '' }))}>
              Clear dates
            </button>
          )}
          <button type="button" className="textlink mb-2" onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="mb-5 rounded-lg border border-berry/40 bg-berry/5 p-3 text-sm font-medium text-berry">
          {error}
        </p>
      )}
      <p role="status" className="mb-4 text-sm opacity-75">
        {loading ? 'Loading…' : data ? `${data.total} request${data.total === 1 ? '' : 's'} shown, by requested date.` : ''}
      </p>

      {data && data.items.length === 0 && !loading && <p className="rounded-[5px] bg-sage p-8 text-sm">No requests match these filters.</p>}

      <ul className="grid gap-4 xl:grid-cols-2">
        {data?.items.map((booking) => (
          <BookingCard key={booking.id} booking={booking} onChanged={load} onAuthError={onAuthError} />
        ))}
      </ul>
    </section>
  )
}

function BookingCard({ booking, onChanged, onAuthError }) {
  const [notes, setNotes] = useState(booking.internal_notes || '')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null) // { kind: 'ok' | 'error', text }

  const run = async (request, okText) => {
    if (busy) return
    setBusy(true)
    setMessage(null)
    try {
      await request()
      setMessage({ kind: 'ok', text: okText })
      await onChanged()
    } catch (err) {
      if (!onAuthError(err)) setMessage({ kind: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  const changeStatus = (status) => {
    if (ACTION_PROMPT[status] && !window.confirm(ACTION_PROMPT[status])) return
    run(() => api(`/owner/bookings/${booking.id}/status`, { method: 'POST', body: { status } }), `Marked as ${status}.`)
  }
  const saveNotes = () =>
    run(() => api(`/owner/bookings/${booking.id}`, { method: 'PATCH', body: { internal_notes: notes } }), 'Notes saved.')

  const notesId = `notes-${booking.id}`
  return (
    <li className="rounded-[5px] border border-line bg-white/60 p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[26px] tracking-[-0.6px]">{booking.full_name}</h2>
          <p className="text-xs tracking-[1px] opacity-70">
            {booking.reference} · received {formatDateTime(booking.created_at)}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[1.5px] ${STATUS_STYLE[booking.status]}`}>{booking.status}</span>
      </div>

      <dl className="my-4 grid grid-cols-[auto_1fr] gap-x-5 gap-y-1.5 text-sm">
        <dt className="opacity-65">When</dt>
        <dd className="font-semibold">
          {formatDate(booking.requested_date)}, {formatTime(booking.requested_time)}
        </dd>
        <dt className="opacity-65">Guests</dt>
        <dd>{booking.party_size}</dd>
        <dt className="opacity-65">Phone</dt>
        <dd>
          <a className="underline" href={`tel:${booking.phone}`}>
            {booking.phone}
          </a>
        </dd>
        {booking.email && (
          <>
            <dt className="opacity-65">Email</dt>
            <dd>
              <a className="break-all underline" href={`mailto:${booking.email}`}>
                {booking.email}
              </a>
            </dd>
          </>
        )}
        {booking.special_requests && (
          <>
            <dt className="opacity-65">Requests</dt>
            <dd className="whitespace-pre-wrap">{booking.special_requests}</dd>
          </>
        )}
        {booking.status_changed_at && (
          <>
            <dt className="opacity-65">Updated</dt>
            <dd>{formatDateTime(booking.status_changed_at)}</dd>
          </>
        )}
      </dl>

      <label className="field-label" htmlFor={notesId}>
        Internal notes <span className="normal-case tracking-normal opacity-70">(never shown to guests)</span>
      </label>
      <textarea id={notesId} rows={2} maxLength={2000} className="field !py-2 text-sm" value={notes} onChange={(e) => setNotes(e.target.value)} />

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {ACTIONS[booking.status].map(([status, label, className]) => (
          <button key={status} type="button" className={`${className} !py-2`} disabled={busy} onClick={() => changeStatus(status)}>
            {label}
          </button>
        ))}
        <button type="button" className="textlink ml-1" disabled={busy || notes === (booking.internal_notes || '')} onClick={saveNotes}>
          Save notes
        </button>
      </div>
      <p role="status" className={`mt-3 min-h-5 text-sm font-medium ${message?.kind === 'error' ? 'text-berry' : ''}`}>
        {message?.text}
      </p>
    </li>
  )
}
