import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AreaShell, SignOutButton } from '../auth/AuthLayout.jsx'
import { Profile } from '../customer/CustomerApp.jsx'
import { api } from '../lib/api.js'
import { useSession } from '../lib/session.jsx'
import { startPolling } from '../lib/status.jsx'
import ActivityPanel from './ActivityPanel.jsx'
import BookingsPanel from './BookingsPanel.jsx'
import InventoryPanel from './InventoryPanel.jsx'
import MenuPanel from './MenuPanel.jsx'
import SettingsPanel from './SettingsPanel.jsx'
import TeamPanel from './TeamPanel.jsx'

const SOUND_KEY = 'wendy.staff.alertSound'
const readSoundPreference = () => {
  try {
    return localStorage.getItem(SOUND_KEY) === 'on'
  } catch {
    return false
  }
}

function beep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    const ctx = new Ctx()
    const gain = ctx.createGain()
    gain.gain.setValueAtTime(0.12, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.6)
    gain.connect(ctx.destination)
    for (const [frequency, start] of [[660, 0], [880, 0.18]]) {
      const osc = ctx.createOscillator()
      osc.frequency.value = frequency
      osc.connect(gain)
      osc.start(ctx.currentTime + start)
      osc.stop(ctx.currentTime + start + 0.25)
    }
    setTimeout(() => ctx.close(), 1000)
  } catch {
    // Sound is optional; the on-screen alert still shows.
  }
}

/**
 * Dashboard for the owner (/owner) and for employees (/employee).
 * Tabs appear according to the account's role and permissions as reported by
 * the server; the server checks every request again regardless.
 */
export default function StaffApp({ portal }) {
  const { account, can, handleAuthError } = useSession()
  const isOwner = account?.role === 'owner'
  const canViewBookings = can('bookings.view_all') || can('bookings.view_assigned')
  const tabs = [
    canViewBookings && ['bookings', 'Table requests'],
    can('booking_settings.manage') && ['settings', 'Booking settings'],
    can('menu.manage') && ['menu', 'Menu'],
    can('inventory.view') && ['inventory', 'Inventory'],
    isOwner && ['team', 'Team'],
    isOwner && ['activity', 'Activity'],
    account && account.role !== 'customer' && ['account', 'My account'],
  ].filter(Boolean)
  // /owner/account and /employee/account open straight on "My account" (linked from the site header).
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const onAccountPath = pathname.replace(/\/+$/, '').endsWith('/account')
  const [tab, setTabState] = useState(onAccountPath ? 'account' : null)
  const setTab = (id) => {
    setTabState(id)
    if (onAccountPath && id !== 'account') navigate(`/${portal}`, { replace: true })
  }
  const active = tabs.some(([id]) => id === tab) ? tab : tabs[0]?.[0]

  // --- alerts for new pending requests (simple polling) ---
  const [alerts, setAlerts] = useState(null)
  const [fresh, setFresh] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [sound, setSound] = useState(readSoundPreference)
  const lastSeen = useRef(null)
  const soundRef = useRef(sound)
  soundRef.current = sound

  const poll = useCallback(async () => {
    try {
      const data = await api('/staff/alerts')
      setAlerts(data)
      const newest = data.newest_pending_id ?? 0
      if (lastSeen.current !== null && newest > lastSeen.current) {
        setFresh(true)
        setRefreshKey((k) => k + 1)
        if (soundRef.current) beep()
      }
      lastSeen.current = Math.max(lastSeen.current ?? 0, newest)
    } catch (err) {
      handleAuthError(err) // other failures: keep the last numbers and try again next time
    }
  }, [handleAuthError])

  // Low-stock count for the Inventory tab label; the panel updates it as it loads.
  const [lowStock, setLowStock] = useState(0)
  const canViewInventory = can('inventory.view')
  useEffect(() => {
    if (!canViewInventory) return
    api('/staff/inventory/items?limit=1')
      .then((data) => setLowStock(data.low_stock_count))
      .catch(() => {}) // the tab still works; the panel reports errors itself
  }, [canViewInventory])

  const role = account?.role
  useEffect(() => {
    if (!role || role === 'customer' || !canViewBookings) return undefined
    poll()
    return startPolling(poll, 20000)
  }, [role, canViewBookings, poll])

  const toggleSound = () => {
    const next = !sound
    setSound(next)
    try {
      localStorage.setItem(SOUND_KEY, next ? 'on' : 'off')
    } catch {
      // Preference just won't be remembered.
    }
    if (next) beep() // lets the browser allow audio, and previews the sound
  }

  const tagline = portal === 'owner' ? 'OWNER DASHBOARD' : 'STAFF DASHBOARD'
  if (account === undefined) {
    return (
      <AreaShell tagline={tagline} title="Dashboard">
        <p role="status">Checking your session…</p>
      </AreaShell>
    )
  }
  if (account === null) return <Navigate to={`/${portal}/login`} replace />
  if (account.role === 'customer') return <Navigate to="/customer" replace />
  if (account.role !== portal) return <Navigate to={account.role === 'owner' ? '/owner' : '/employee'} replace />

  return (
    <AreaShell
      tagline={tagline}
      title={portal === 'owner' ? 'Owner dashboard' : 'Staff dashboard'}
      right={
        <>
          <span className="hidden sm:inline">
            {account.full_name} · {account.email}
          </span>
          <SignOutButton />
        </>
      }
    >
      {tabs.length <= 1 && account.role === 'employee' && (
        <div role="alert" className="mb-8 max-w-xl rounded-[20px] border border-line bg-white/60 p-8">
          <h1 className="mb-3 text-[32px]">You don’t have access to anything yet.</h1>
          <p className="text-sm">Your account is active, but the owner has not given it any permissions. Please ask the owner.</p>
        </div>
      )}
      {tabs.length === 0 ? null : (
        <>
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <div role="group" aria-label="Dashboard sections" className="flex flex-wrap gap-2">
              {tabs.map(([id, label]) => (
                <button key={id} type="button" aria-pressed={active === id} className="chip" onClick={() => setTab(id)}>
                  {label}
                  {id === 'bookings' && alerts?.pending_count ? ` · ${alerts.pending_count} waiting` : ''}
                  {id === 'inventory' && lowStock ? ` · ${lowStock} low` : ''}
                </button>
              ))}
            </div>
            {canViewBookings && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-forest" checked={sound} onChange={toggleSound} />
                Sound for new requests
              </label>
            )}
          </div>

          {fresh && (
            <div role="status" className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-[20px] border border-amber bg-citrus/60 px-5 py-3 text-sm">
              <strong>A new table request has arrived.</strong>
              <span className="flex gap-4">
                {active !== 'bookings' && (
                  <button type="button" className="textlink" onClick={() => { setTab('bookings'); setFresh(false) }}>
                    View requests
                  </button>
                )}
                <button type="button" className="textlink" onClick={() => setFresh(false)}>
                  Dismiss
                </button>
              </span>
            </div>
          )}
          {alerts?.cancellation_requests > 0 && active === 'bookings' && (
            <p role="status" className="mb-6 rounded-[20px] border border-line bg-white/60 px-5 py-3 text-sm">
              {alerts.cancellation_requests} cancellation request{alerts.cancellation_requests === 1 ? '' : 's'} waiting for an answer.
            </p>
          )}

          {active === 'bookings' && <BookingsPanel refreshKey={refreshKey} onChanged={poll} />}
          {active === 'settings' && <SettingsPanel onAuthError={handleAuthError} />}
          {active === 'menu' && <MenuPanel onAuthError={handleAuthError} />}
          {active === 'inventory' && <InventoryPanel onLowCount={setLowStock} />}
          {active === 'team' && <TeamPanel />}
          {active === 'activity' && <ActivityPanel />}
          {active === 'account' && <Profile />}
        </>
      )}
      {account.role === 'employee' && (
        <p className="mt-10 text-xs opacity-70">
          What you can see and do here is set by the owner. <Link className="underline" to="/account/forgot">Forgot your password?</Link>
        </p>
      )}
    </AreaShell>
  )
}
