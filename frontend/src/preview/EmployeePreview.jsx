import { useState } from 'react'
import { AreaShell } from '../auth/AuthLayout.jsx'
import { formatDate, formatTime } from '../lib/time.js'
import { PREVIEW_BOOKINGS, PREVIEW_EMPLOYEE } from './fixtures.js'
import { PERMISSION_SETS, PERMISSIONS } from './permissions.js'
import PreviewBanner, { STATUS_LABEL, StatusBadge } from './PreviewBanner.jsx'

const STATUSES = ['pending', 'confirmed', 'checked_in', 'declined', 'cancelled']

/** Design preview of the staff area. Fictional data, in memory only, no API calls. */
export default function EmployeePreview() {
  const [setKey, setSetKey] = useState('host')
  const [bookings, setBookings] = useState(PREVIEW_BOOKINGS)
  const [status, setStatus] = useState('')
  const [date, setDate] = useState('')
  const [openId, setOpenId] = useState(null)
  const [notice, setNotice] = useState('')

  const granted = PERMISSION_SETS[setKey].permissions
  const can = (key) => granted.includes(key)
  const shown = bookings
    .filter((b) => (!status || b.status === status) && (!date || b.requested_date === date))
    .sort((a, b) => `${a.requested_date}${a.requested_time}`.localeCompare(`${b.requested_date}${b.requested_time}`))

  const change = (id, next) => {
    setBookings((list) => list.map((b) => (b.id === id ? { ...b, status: next } : b)))
    setNotice(`Marked as ${STATUS_LABEL[next].toLowerCase()} in this preview only. Nothing was saved.`)
  }

  const actionsFor = (b) =>
    [
      b.status === 'pending' && can('approve_decline') && ['confirmed', 'Approve', 'pill pill-dark'],
      b.status === 'pending' && can('approve_decline') && ['declined', 'Decline', 'pill'],
      b.status === 'confirmed' && can('check_in') && ['checked_in', 'Check in', 'pill pill-dark'],
      ['pending', 'confirmed'].includes(b.status) && can('cancel') && ['cancelled', 'Cancel', 'pill'],
    ].filter(Boolean)

  return (
    <AreaShell
      tagline="STAFF"
      title="Staff bookings (preview)"
      banner={<PreviewBanner />}
      right={<span className="hidden sm:inline">{PREVIEW_EMPLOYEE.email}</span>}
    >
      <div className="mb-8 rounded-[20px] bg-sage p-5">
        <label className="field-label" htmlFor="permission-set">
          Preview as an employee with…
        </label>
        <select id="permission-set" className="field max-w-xs" value={setKey} onChange={(e) => { setSetKey(e.target.value); setNotice('') }}>
          {Object.entries(PERMISSION_SETS).map(([key, set]) => (
            <option key={key} value={key}>
              {set.label}
            </option>
          ))}
        </select>
        <ul className="mt-4 flex flex-wrap gap-2 text-xs" aria-label="Permissions in this preview">
          {PERMISSIONS.map((p) => (
            <li key={p.key} className={`rounded-full border px-3 py-1 ${can(p.key) ? 'border-forest bg-forest text-cream' : 'border-line line-through opacity-60'}`}>
              {p.label}
              <span className="sr-only">{can(p.key) ? ' (allowed)' : ' (not allowed)'}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs opacity-75">In the finished site the owner sets these, and the server checks them on every action.</p>
      </div>

      <h1 className="mb-6 text-[40px]">Bookings</h1>

      {!can('view_bookings') ? (
        <div role="alert" className="max-w-xl rounded-[20px] border border-line bg-white/60 p-8">
          <h2 className="mb-3 text-[28px] tracking-[-0.6px]">You don’t have access to bookings.</h2>
          <p className="text-sm">Your account isn’t allowed to view table requests. Ask the owner to give you the “View bookings” permission.</p>
        </div>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-end gap-4">
            <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
              <button type="button" className="chip" aria-pressed={!status} onClick={() => setStatus('')}>
                All
              </button>
              {STATUSES.map((s) => (
                <button key={s} type="button" className="chip" aria-pressed={status === s} onClick={() => setStatus(s)}>
                  {STATUS_LABEL[s]}
                </button>
              ))}
            </div>
            <label className="text-xs font-semibold uppercase tracking-[1.5px]">
              Date
              <input type="date" className="field mt-1 !py-2 font-normal normal-case tracking-normal" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            {date && (
              <button type="button" className="textlink mb-2" onClick={() => setDate('')}>
                Clear date
              </button>
            )}
          </div>

          <p role="status" className="mb-4 min-h-5 text-sm font-medium">
            {notice}
          </p>

          {shown.length === 0 && <p className="rounded-[20px] bg-sage p-8 text-sm">No bookings match these filters.</p>}

          <ul className="grid gap-4 xl:grid-cols-2">
            {shown.map((b) => {
              const open = openId === b.id
              const actions = actionsFor(b)
              return (
                <li key={b.id} className="rounded-[20px] border border-line bg-white/60 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-[24px] tracking-[-0.6px]">{b.full_name}</h2>
                      <p className="text-sm">
                        {formatDate(b.requested_date)}, {formatTime(b.requested_time)} · {b.party_size} guests
                      </p>
                    </div>
                    <StatusBadge status={b.status} />
                  </div>
                  <button type="button" className="textlink mt-3" aria-expanded={open} onClick={() => setOpenId(open ? null : b.id)}>
                    {open ? 'Hide details' : 'View details'}
                  </button>
                  {open && (
                    <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-5 gap-y-1.5 border-t border-line pt-4 text-sm">
                      <dt className="opacity-65">Reference</dt>
                      <dd>{b.reference}</dd>
                      <dt className="opacity-65">Contact</dt>
                      <dd>
                        {can('view_contact') ? (
                          <>
                            {b.phone}
                            {b.email ? ` · ${b.email}` : ''}
                          </>
                        ) : (
                          <span className="italic opacity-75">Hidden. You don’t have permission to view contact details.</span>
                        )}
                      </dd>
                      <dt className="opacity-65">Requests</dt>
                      <dd>{b.special_requests || 'None'}</dd>
                    </dl>
                  )}
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    {actions.map(([next, label, className]) => (
                      <button key={next} type="button" className={`${className} !py-2`} onClick={() => change(b.id, next)}>
                        {label}
                      </button>
                    ))}
                    {actions.length === 0 && ['pending', 'confirmed'].includes(b.status) && (
                      <p className="text-xs italic opacity-75">You can view this booking but don’t have permission to change it.</p>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </AreaShell>
  )
}
