import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { whatsappLink } from '../lib/business.js'
import { useSession } from '../lib/session.jsx'
import { STATUS_LABEL, StatusBadge } from '../lib/status.jsx'
import { formatDate, formatDateTime, formatTime } from '../lib/time.js'

const STATUSES = ['pending', 'confirmed', 'checked_in', 'completed', 'declined', 'cancelled', 'no_show']
const ACTION = {
  confirmed: { label: 'Confirm', className: 'pill pill-dark' },
  declined: { label: 'Decline', className: 'pill', ask: 'Decline this request? This cannot be undone.\n\nOptional: add a reason for your records.' },
  cancelled: { label: 'Cancel booking', className: 'pill', ask: 'Cancel this booking? This cannot be undone.\n\nOptional: add a reason for your records.' },
  checked_in: { label: 'Check in', className: 'pill pill-dark' },
  completed: { label: 'Mark completed', className: 'pill pill-dark' },
  no_show: { label: 'No-show', className: 'pill', ask: 'Mark this booking as a no-show? This cannot be undone.\n\nOptional: add a note.' },
}

export default function BookingsPanel({ refreshKey, onChanged }) {
  const { account, handleAuthError } = useSession()
  const isOwner = account.role === 'owner'
  const [filters, setFilters] = useState({ status: 'pending', date_from: '', date_to: '', cancellation: '' })
  const [data, setData] = useState(null)
  const [employees, setEmployees] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString()
    try {
      setData(await api(`/staff/bookings${query ? `?${query}` : ''}`))
    } catch (err) {
      if (!handleAuthError(err)) setError(err.status === 403 ? 'You no longer have permission to view bookings.' : err.message)
    } finally {
      setLoading(false)
    }
  }, [filters, handleAuthError])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  useEffect(() => {
    if (isOwner) api('/staff/assignable').then(setEmployees).catch(() => {})
  }, [isOwner])

  const changed = useCallback(async () => {
    await load()
    onChanged?.()
  }, [load, onChanged])

  const setFilter = (name, value) => setFilters((f) => ({ ...f, [name]: value }))
  const total = data ? Object.values(data.counts).reduce((a, b) => a + b, 0) : 0

  return (
    <section aria-labelledby="bookings-title">
      <h1 id="bookings-title" className="mb-2 text-[40px]">
        Table requests
      </h1>
      <p className="mb-6 max-w-2xl text-sm opacity-80">
        Guests are told their table is <strong>not confirmed</strong> until the team contacts them. This dashboard does not
        track tables or seats and sends no messages: check availability yourself, contact the guest, then record the outcome
        here.{data?.scope === 'assigned' ? ' You are shown only the bookings assigned to you.' : ''}
      </p>

      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
          <button type="button" className="chip" aria-pressed={!filters.status} onClick={() => setFilter('status', '')}>
            All{data ? ` (${total})` : ''}
          </button>
          {STATUSES.map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={filters.status === s} onClick={() => setFilter('status', s)}>
              {STATUS_LABEL[s]}
              {data ? ` (${data.counts[s] ?? 0})` : ''}
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
          <label className="mb-2 flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-forest" checked={Boolean(filters.cancellation)} onChange={(e) => setFilter('cancellation', e.target.checked ? 'pending' : '')} />
            Cancellation requests only
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

      {data && data.items.length === 0 && !loading && <p className="rounded-[20px] bg-sage p-8 text-sm">No requests match these filters.</p>}

      <ul className="grid gap-4 xl:grid-cols-2">
        {data?.items.map((booking) => (
          <BookingCard key={`${booking.id}-${booking.version}`} booking={booking} employees={employees} isOwner={isOwner} onChanged={changed} />
        ))}
      </ul>
    </section>
  )
}

function BookingCard({ booking, employees, isOwner, onChanged }) {
  const { handleAuthError } = useSession()
  const [notes, setNotes] = useState(booking.internal_notes || '')
  const [reply, setReply] = useState('')
  const [history, setHistory] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null) // { ok, text }

  // Every change sends the version this card was drawn with. If someone else
  // changed the booking meanwhile, the server refuses and the list reloads.
  const run = async (request, okText) => {
    if (busy) return
    setBusy(true)
    setMessage(null)
    try {
      await request()
      setMessage({ ok: true, text: okText })
      await onChanged()
    } catch (err) {
      if (handleAuthError(err)) return
      setMessage({ ok: false, text: err.message })
      if (err.status === 409 || err.status === 404 || err.status === 403) await onChanged()
    } finally {
      setBusy(false)
    }
  }

  const changeStatus = (status) => {
    let reason = null
    if (ACTION[status].ask) {
      reason = window.prompt(ACTION[status].ask, '')
      if (reason === null) return
    }
    run(() => api(`/staff/bookings/${booking.id}/status`, { method: 'POST', body: { status, version: booking.version, reason: reason || null } }), `Marked as ${STATUS_LABEL[status].toLowerCase()}.`)
  }
  const saveNotes = () => run(() => api(`/staff/bookings/${booking.id}`, { method: 'PATCH', body: { internal_notes: notes, version: booking.version } }), 'Notes saved.')
  const assign = (value) =>
    run(() => api(`/staff/bookings/${booking.id}/assign`, { method: 'POST', body: { employee_id: value ? Number(value) : null, version: booking.version } }), 'Assignment saved.')
  const resolve = (decision) =>
    run(
      () => api(`/staff/bookings/${booking.id}/cancellation`, { method: 'POST', body: { decision, version: booking.version, response: reply.trim() || null } }),
      decision === 'approve' ? 'Cancellation accepted; the booking is cancelled.' : 'Cancellation request declined; the booking stands.',
    )
  const toggleHistory = async () => {
    if (history) return setHistory(null)
    try {
      setHistory((await api(`/staff/bookings/${booking.id}`)).history)
    } catch (err) {
      if (!handleAuthError(err)) setMessage({ ok: false, text: err.message })
    }
  }

  const when = `${formatDate(booking.requested_date)}, ${formatTime(booking.requested_time)}`
  const notesId = `notes-${booking.id}`
  return (
    <li className="rounded-[20px] border border-line bg-white/60 p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[26px] tracking-[-0.6px]">{booking.full_name}</h2>
          <p className="text-xs tracking-[1px] opacity-70">
            {booking.reference} · received {formatDateTime(booking.created_at)} · {booking.has_account ? 'customer account' : 'guest request'}
          </p>
        </div>
        <StatusBadge status={booking.status} />
      </div>

      <dl className="my-4 grid grid-cols-[auto_1fr] gap-x-5 gap-y-1.5 text-sm">
        <dt className="opacity-65">When</dt>
        <dd className="font-semibold">{when}</dd>
        <dt className="opacity-65">Guests</dt>
        <dd>{booking.party_size}</dd>
        <dt className="opacity-65">Contact</dt>
        <dd>
          {booking.contact_visible ? (
            <>
              <a className="underline" href={`tel:${booking.phone}`}>
                {booking.phone}
              </a>
              {booking.email && (
                <>
                  {' · '}
                  <a className="break-all underline" href={`mailto:${booking.email}`}>
                    {booking.email}
                  </a>
                </>
              )}
              <br />
              <a
                className="text-xs underline"
                target="_blank"
                rel="noopener noreferrer"
                href={whatsappLink(booking.phone, `Hello ${booking.full_name}, this is Wendy Juice Shop about your table request ${booking.reference} for ${when}.`)}
              >
                Open WhatsApp with a message to send
              </a>
              <span className="text-xs opacity-65"> (you press send; nothing is sent from here)</span>
            </>
          ) : (
            <span className="italic opacity-75">Hidden. You don’t have permission to view contact details.</span>
          )}
        </dd>
        {booking.special_requests && (
          <>
            <dt className="opacity-65">Requests</dt>
            <dd className="whitespace-pre-wrap">{booking.special_requests}</dd>
          </>
        )}
        <dt className="opacity-65">Assigned</dt>
        <dd>
          {isOwner ? (
            <select aria-label={`Assign ${booking.reference} to`} className="field !w-auto !py-1.5 text-sm" disabled={busy} value={booking.assigned_employee?.id ?? ''} onChange={(e) => assign(e.target.value)}>
              <option value="">Nobody</option>
              {booking.assigned_employee && !employees.some((e) => e.id === booking.assigned_employee.id) && (
                <option value={booking.assigned_employee.id}>{booking.assigned_employee.full_name}</option>
              )}
              {employees.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.full_name}
                </option>
              ))}
            </select>
          ) : (
            booking.assigned_employee?.full_name || 'Nobody'
          )}
        </dd>
      </dl>

      {booking.cancellation && (
        <div className={`mb-4 rounded-lg p-4 text-sm ${booking.cancellation.status === 'pending' ? 'border border-amber bg-citrus/40' : 'bg-sage'}`}>
          <p className="font-semibold">
            {booking.cancellation.status === 'pending' ? 'The customer has asked to cancel.' : `Cancellation request ${booking.cancellation.status}.`}
          </p>
          {booking.cancellation.reason && <p className="mt-1">Reason: “{booking.cancellation.reason}”</p>}
          {booking.cancellation.response && <p className="mt-1">Reply sent to customer’s page: “{booking.cancellation.response}”</p>}
          {booking.can_resolve_cancellation && (
            <>
              <label className="field-label mt-3" htmlFor={`reply-${booking.id}`}>
                Reply shown to the customer (optional)
              </label>
              <input id={`reply-${booking.id}`} className="field mb-3 !py-2 text-sm" maxLength={500} value={reply} onChange={(e) => setReply(e.target.value)} />
              <div className="flex flex-wrap gap-2">
                <button type="button" className="pill pill-dark !py-2" disabled={busy} onClick={() => resolve('approve')}>
                  Accept and cancel
                </button>
                <button type="button" className="pill !py-2" disabled={busy} onClick={() => resolve('decline')}>
                  Keep the booking
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <label className="field-label" htmlFor={notesId}>
        Internal notes <span className="normal-case tracking-normal opacity-70">(never shown to guests)</span>
      </label>
      <textarea id={notesId} rows={2} maxLength={2000} className="field !py-2 text-sm" value={notes} readOnly={!booking.can_edit_notes} onChange={(e) => setNotes(e.target.value)} />

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {booking.allowed_statuses.map((status) => (
          <button key={status} type="button" className={`${ACTION[status].className} !py-2`} disabled={busy} onClick={() => changeStatus(status)}>
            {ACTION[status].label}
          </button>
        ))}
        {booking.can_edit_notes && (
          <button type="button" className="textlink ml-1" disabled={busy || notes === (booking.internal_notes || '')} onClick={saveNotes}>
            Save notes
          </button>
        )}
        <button type="button" className="textlink ml-1" aria-expanded={Boolean(history)} onClick={toggleHistory}>
          {history ? 'Hide history' : 'History'}
        </button>
      </div>
      {booking.allowed_statuses.length === 0 && ['pending', 'confirmed', 'checked_in'].includes(booking.status) && (
        <p className="mt-2 text-xs italic opacity-75">No status change is available to you for this booking right now.</p>
      )}

      {history && (
        <ol className="mt-4 space-y-1.5 border-t border-line pt-4 text-sm">
          {history.map((entry, i) => (
            <li key={i}>
              <span className="opacity-65">{formatDateTime(entry.created_at)}</span> · {entry.from_status ? `${STATUS_LABEL[entry.from_status]} → ` : ''}
              <strong>{STATUS_LABEL[entry.to_status]}</strong> by {entry.actor}
              {entry.reason ? ` — ${entry.reason}` : ''}
            </li>
          ))}
        </ol>
      )}
      <p role={message && !message.ok ? 'alert' : 'status'} className={`mt-3 min-h-5 text-sm font-medium ${message && !message.ok ? 'text-berry' : ''}`}>
        {message?.text}
      </p>
    </li>
  )
}
