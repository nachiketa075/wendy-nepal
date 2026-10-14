import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { useSession } from '../lib/session.jsx'
import { formatDateTime } from '../lib/time.js'

const ACTIONS = {
  'booking.status': (d) => `changed a booking from ${d.from_status} to ${d.to_status}${d.reason ? ` (“${d.reason}”)` : ''}`,
  'booking.notes': () => 'edited a booking’s internal notes',
  'booking.assign': (d) => (d.employee ? `assigned a booking to ${d.employee}` : 'unassigned a booking'),
  'booking.cancellation_requested': () => 'asked to cancel their booking',
  'booking.cancellation_resolved': (d) => `${d.decision} a cancellation request`,
  'employee.created': (d) => `added employee ${d.email}`,
  'employee.permissions_changed': (d) => `changed permissions (${(d.after || []).length} now allowed)`,
  'employee.deactivated': () => 'deactivated an employee',
  'employee.reactivated': () => 'reactivated an employee',
  'employee.sessions_revoked': () => 'signed an employee out everywhere',
  'employee.setup_link_issued': () => 'created a new password link for an employee',
  'settings.updated': () => 'changed the booking settings',
  'menu.item_created': (d) => `added menu item “${d.name}”`,
  'menu.item_updated': (d) => `edited menu item “${d.name}”`,
  'menu.item_deleted': (d) => `deleted menu item “${d.name}”`,
  'menu.category_created': (d) => `added menu section “${d.name}”`,
  'menu.category_updated': () => 'edited a menu section',
  'menu.category_deleted': (d) => `deleted menu section “${d.name}”`,
  'inventory.item_created': (d) => `added inventory item “${d.name}” (opening stock ${d.opening})`,
  'inventory.item_updated': (d) => `edited inventory item “${d.name}” (${(d.fields || []).join(', ')})`,
  'inventory.item_archived': (d) => `archived inventory item “${d.name}”`,
  'inventory.item_restored': (d) => `restored inventory item “${d.name}”`,
  'inventory.stock_corrected': (d) => `corrected stock of “${d.name}” by ${d.change} to ${d.balance} (“${d.reason}”)`,
  'account.password_changed': () => 'changed their password',
  'account.password_reset': () => 'reset their password by link',
  'account.password_set': () => 'chose their first password',
}

/** Owner only: who did what, newest first. */
export default function ActivityPanel() {
  const { handleAuthError } = useSession()
  const [limit, setLimit] = useState(50)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setData(await api(`/owner/activity?limit=${limit}`))
    } catch (err) {
      if (!handleAuthError(err)) setError(err.message)
    }
  }, [limit, handleAuthError])

  useEffect(() => {
    load()
  }, [load])

  return (
    <section aria-labelledby="activity-title">
      <h1 id="activity-title" className="mb-2 text-[40px]">
        Activity
      </h1>
      <p className="mb-6 max-w-2xl text-sm opacity-80">A record of changes made by you, your team and customers. Guest contact details are not copied here.</p>
      {error && (
        <p role="alert" className="mb-5 rounded-lg border border-berry/40 bg-berry/5 p-3 text-sm font-medium text-berry">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">Loading…</p>}
      {data && data.items.length === 0 && <p className="rounded-[20px] bg-sage p-8 text-sm">Nothing has been recorded yet.</p>}
      {data && data.items.length > 0 && (
        <ol className="divide-y divide-line border-y border-line">
          {data.items.map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-3 text-sm">
              <span className="w-[130px] shrink-0 text-xs opacity-65">{formatDateTime(entry.created_at)}</span>
              <span className="flex-1">
                <strong>{entry.actor_label}</strong> <span className="text-xs uppercase tracking-[1px] opacity-60">{entry.actor_role}</span>{' '}
                {(ACTIONS[entry.action] || (() => entry.action))(entry.detail || {})}
                {entry.target_type === 'booking' && entry.target_id ? ` · ${entry.target_id}` : ''}
              </span>
            </li>
          ))}
        </ol>
      )}
      <div className="mt-5 flex flex-wrap items-center gap-4">
        {data && data.total > data.items.length && (
          <button type="button" className="pill" onClick={() => setLimit((n) => Math.min(200, n + 50))}>
            Show more
          </button>
        )}
        <button type="button" className="textlink" onClick={load}>
          Refresh
        </button>
      </div>
    </section>
  )
}
