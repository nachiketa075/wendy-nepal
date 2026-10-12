import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ErrorNote, Field } from '../auth/AccountPages.jsx'
import { AreaShell } from '../auth/AuthLayout.jsx'
import { api } from '../lib/api.js'
import { BUSINESS } from '../lib/business.js'
import { useSession } from '../lib/session.jsx'
import { StatusBadge, startPolling } from '../lib/status.jsx'
import { formatDate, formatDateTime, formatTime } from '../lib/time.js'

const STATUS_NOTE = {
  pending: 'Not confirmed yet. The team will contact you after checking availability.',
  confirmed: 'Confirmed by the team. See you then.',
  declined: 'Sorry, we could not fit this request in.',
  cancelled: 'This booking was cancelled.',
  checked_in: 'You have arrived. Enjoy!',
  completed: 'Thanks for visiting.',
  no_show: 'Marked as not attended.',
}

export default function CustomerApp() {
  const { account, signOut } = useSession()
  const { pathname } = useLocation()

  if (account === undefined) {
    return (
      <AreaShell tagline="MY ACCOUNT" title="My account">
        <p role="status">Checking your session…</p>
      </AreaShell>
    )
  }
  if (account === null) return <Navigate to="/customer/login" replace />
  if (account.role !== 'customer') {
    return (
      <AreaShell tagline="MY ACCOUNT" title="My account">
        <div role="alert" className="max-w-xl rounded-[20px] bg-sage p-8">
          <h1 className="mb-3 text-[32px]">This page is for customer accounts.</h1>
          <p className="mb-5 text-sm">
            You are signed in as {account.email} ({account.role}).
          </p>
          <Link className="pill pill-dark" to={account.role === 'owner' ? '/owner' : '/employee'}>
            Go to the staff dashboard
          </Link>
        </div>
      </AreaShell>
    )
  }

  const onProfile = pathname.replace(/\/+$/, '').endsWith('/profile')
  return (
    <AreaShell
      tagline="MY ACCOUNT"
      title={onProfile ? 'My profile' : 'My bookings'}
      right={
        <>
          <span className="hidden sm:inline">{account.email}</span>
          <button type="button" className="pill !py-2" onClick={signOut}>
            Sign out
          </button>
        </>
      }
    >
      <nav aria-label="Account sections" className="mb-8 flex flex-wrap gap-2">
        <Link to="/customer" className="chip" aria-current={!onProfile ? 'page' : undefined}>
          My bookings
        </Link>
        <Link to="/customer/profile" className="chip" aria-current={onProfile ? 'page' : undefined}>
          Profile
        </Link>
        <a href="/#book" className="chip">
          Request a table
        </a>
      </nav>
      <Routes>
        <Route path="profile" element={<Profile />} />
        <Route path="*" element={<Bookings />} />
      </Routes>
    </AreaShell>
  )
}

function Bookings() {
  const { handleAuthError } = useSession()
  const [state, setState] = useState({ status: 'loading', upcoming: [], past: [], pastTotal: 0 })
  const [pastLimit, setPastLimit] = useState(10)

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setState((s) => ({ ...s, status: s.status === 'ready' ? 'ready' : 'loading' }))
      try {
        const [upcoming, past] = await Promise.all([
          api('/customer/bookings?when=upcoming&limit=50'),
          api(`/customer/bookings?when=past&limit=${pastLimit}`),
        ])
        setState({ status: 'ready', upcoming: upcoming.items, past: past.items, pastTotal: past.total })
      } catch (err) {
        if (handleAuthError(err)) return
        // A background refresh that fails leaves what is on screen; the next one retries.
        if (!quiet) setState((s) => ({ ...s, status: 'error', message: err.message }))
      }
    },
    [handleAuthError, pastLimit],
  )

  useEffect(() => {
    load()
    // Refresh quietly so a confirmation by staff shows up without reloading.
    return startPolling(() => load(true), 30000)
  }, [load])

  if (state.status === 'loading') return <p role="status">Loading your bookings…</p>
  if (state.status === 'error') {
    return (
      <div role="alert" className="max-w-xl rounded-lg border border-berry/40 bg-berry/5 p-5 text-sm text-berry">
        <p className="font-semibold">We couldn’t load your bookings.</p>
        <p className="mt-1">{state.message}</p>
        <button type="button" className="pill mt-4 !py-2 text-forest" onClick={() => load()}>
          Try again
        </button>
      </div>
    )
  }
  if (state.upcoming.length === 0 && state.past.length === 0) {
    return (
      <div className="max-w-xl rounded-[20px] bg-sage p-8">
        <h1 className="mb-3 text-[36px]">No bookings yet.</h1>
        <p className="mb-5 text-sm">When you ask for a table while signed in, it will show up here with its status.</p>
        <a className="pill pill-dark" href="/#book">
          Request a table
        </a>
      </div>
    )
  }

  return (
    <>
      <h1 className="mb-6 text-[40px]">My bookings</h1>
      <section aria-labelledby="upcoming-title" className="mb-10">
        <h2 id="upcoming-title" className="mb-4 text-[28px] tracking-[-0.6px]">
          Upcoming
        </h2>
        {state.upcoming.length ? (
          <ul className="grid gap-4 lg:grid-cols-2">
            {state.upcoming.map((b) => (
              <BookingCard key={b.reference} booking={b} onChanged={() => load(true)} />
            ))}
          </ul>
        ) : (
          <p className="text-sm">Nothing coming up.</p>
        )}
      </section>
      {state.past.length > 0 && (
        <section aria-labelledby="past-title">
          <h2 id="past-title" className="mb-4 text-[28px] tracking-[-0.6px]">
            Past
          </h2>
          <ul className="grid gap-4 lg:grid-cols-2">
            {state.past.map((b) => (
              <BookingCard key={b.reference} booking={b} onChanged={() => load(true)} />
            ))}
          </ul>
          {state.pastTotal > state.past.length && (
            <button type="button" className="pill mt-6" onClick={() => setPastLimit((n) => n + 10)}>
              Show older bookings
            </button>
          )}
        </section>
      )}
    </>
  )
}

function BookingCard({ booking, onChanged }) {
  const { handleAuthError } = useSession()
  const [open, setOpen] = useState(false)
  const [asking, setAsking] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const cancellation = booking.cancellation

  const ask = async () => {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await api(`/customer/bookings/${booking.reference}/cancellation-request`, { method: 'POST', body: { reason: reason.trim() || null } })
      setAsking(false)
      setReason('')
      await onChanged() // show what the server now holds
    } catch (err) {
      if (!handleAuthError(err)) setError(`Your request was not sent. ${err.message}`)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="rounded-[20px] border border-line bg-white/60 p-5">
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
      <p className="mt-3 text-sm">{STATUS_NOTE[booking.status]}</p>

      {cancellation?.status === 'pending' && (
        <p role="status" className="mt-3 rounded-lg bg-citrus/50 p-3 text-sm">
          You asked to cancel this booking on {formatDateTime(cancellation.requested_at)}. The team has not answered yet, so it is still{' '}
          {booking.status}.
        </p>
      )}
      {cancellation?.status === 'approved' && (
        <p className="mt-3 rounded-lg bg-sage p-3 text-sm">
          Your cancellation request was accepted.{cancellation.response ? ` “${cancellation.response}”` : ''}
        </p>
      )}
      {cancellation?.status === 'declined' && (
        <p className="mt-3 rounded-lg border border-berry/30 bg-berry/5 p-3 text-sm">
          Your cancellation request was not accepted, so the booking stands.{cancellation.response ? ` “${cancellation.response}”` : ''} Please call{' '}
          {BUSINESS.phoneDisplay} if you need help.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-4">
        <button type="button" className="textlink" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide details' : 'View details'}
        </button>
        {booking.can_request_cancellation && !asking && (
          <button type="button" className="textlink" onClick={() => setAsking(true)}>
            Ask to cancel
          </button>
        )}
      </div>

      {asking && (
        <div className="mt-4 rounded-lg border border-forest/25 p-4 text-sm">
          <p className="mb-3">This sends a request to the team. Your booking is only cancelled once they accept it.</p>
          <label className="field-label" htmlFor={`reason-${booking.reference}`}>
            Reason (optional)
          </label>
          <textarea id={`reason-${booking.reference}`} rows={2} maxLength={500} className="field mb-3 !py-2 text-sm" value={reason} onChange={(e) => setReason(e.target.value)} />
          {error && <ErrorNote>{error}</ErrorNote>}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="pill pill-dark !py-2" disabled={busy} onClick={ask}>
              {busy ? 'Sending…' : 'Send cancellation request'}
            </button>
            <button type="button" className="pill !py-2" disabled={busy} onClick={() => setAsking(false)}>
              Keep my booking
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
          {booking.email && (
            <>
              <dt className="opacity-65">Email</dt>
              <dd className="break-all">{booking.email}</dd>
            </>
          )}
          <dt className="opacity-65">Requests</dt>
          <dd className="whitespace-pre-wrap">{booking.special_requests || 'None'}</dd>
          <dt className="opacity-65">Sent</dt>
          <dd>{formatDateTime(booking.created_at)} (Pokhara time)</dd>
        </dl>
      )}
    </li>
  )
}

export function Profile() {
  const { account, apply, handleAuthError } = useSession()
  const [form, setForm] = useState({ full_name: account.full_name, phone: account.phone || '' })
  const [errors, setErrors] = useState({})
  const [note, setNote] = useState(null)
  const [busy, setBusy] = useState(false)
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' })
  const [passwordErrors, setPasswordErrors] = useState({})
  const [passwordNote, setPasswordNote] = useState(null)
  const [passwordBusy, setPasswordBusy] = useState(false)

  const saveProfile = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setNote(null)
    setErrors({})
    try {
      apply(await api('/auth/profile', { method: 'PATCH', body: { full_name: form.full_name.trim(), phone: form.phone.trim() || null } }))
      setNote({ ok: true, text: 'Profile saved.' })
    } catch (err) {
      if (handleAuthError(err)) return
      setErrors(err.fields || {})
      setNote({ ok: false, text: `Not saved. ${Object.keys(err.fields || {}).length ? 'Please check the highlighted details.' : err.message}` })
    } finally {
      setBusy(false)
    }
  }

  const savePassword = async (event) => {
    event.preventDefault()
    if (passwordBusy) return
    if (passwords.new_password.length < 12) return setPasswordErrors({ new_password: 'Use at least 12 characters.' })
    setPasswordBusy(true)
    setPasswordNote(null)
    setPasswordErrors({})
    try {
      await api('/auth/password', { method: 'POST', body: passwords })
      setPasswords({ current_password: '', new_password: '' })
      setPasswordNote({ ok: true, text: 'Password changed. Other devices were signed out.' })
    } catch (err) {
      if (handleAuthError(err)) return
      setPasswordErrors(err.fields || {})
      setPasswordNote({ ok: false, text: `Not changed. ${Object.keys(err.fields || {}).length ? 'Please check the highlighted details.' : err.message}` })
    } finally {
      setPasswordBusy(false)
    }
  }

  const Note = ({ value }) => (
    <p role={value && !value.ok ? 'alert' : 'status'} className={`mt-3 min-h-5 text-sm font-medium ${value && !value.ok ? 'text-berry' : ''}`}>
      {value?.text}
    </p>
  )

  return (
    <div className="grid max-w-4xl gap-8 lg:grid-cols-2">
      <form onSubmit={saveProfile} className="rounded-[20px] bg-sage p-6 md:p-8" noValidate>
        <h1 className="mb-5 text-[32px]">Profile</h1>
        <Field id="profile-email" label="Email" value={account.email} readOnly disabled hint="Your sign-in email cannot be changed here." />
        <Field id="profile-name" label="Full name" maxLength={120} autoComplete="name" value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} error={errors.full_name} />
        <Field id="profile-phone" label="Phone" type="tel" maxLength={32} autoComplete="tel" placeholder="+977 98XXXXXXXX" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} error={errors.phone} hint="With country code." />
        <button type="submit" className="pill pill-dark" disabled={busy}>
          {busy ? 'Saving…' : 'Save profile'}
        </button>
        <Note value={note} />
      </form>
      <form onSubmit={savePassword} className="rounded-[20px] bg-sage p-6 md:p-8" noValidate>
        <h2 className="mb-5 text-[32px]">Change password</h2>
        <Field id="current-password" label="Current password" type="password" autoComplete="current-password" value={passwords.current_password} onChange={(e) => setPasswords((p) => ({ ...p, current_password: e.target.value }))} error={passwordErrors.current_password} />
        <Field id="new-password" label="New password" type="password" autoComplete="new-password" maxLength={256} value={passwords.new_password} onChange={(e) => setPasswords((p) => ({ ...p, new_password: e.target.value }))} error={passwordErrors.new_password} hint="At least 12 characters." />
        <button type="submit" className="pill pill-dark" disabled={passwordBusy}>
          {passwordBusy ? 'Saving…' : 'Change password'}
        </button>
        <Note value={passwordNote} />
      </form>
    </div>
  )
}
