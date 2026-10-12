import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../lib/api.js'
import { BUSINESS } from '../lib/business.js'
import { HOME_FOR_ROLE, useSession } from '../lib/session.jsx'
import { AreaShell, LoginCard } from './AuthLayout.jsx'

const PORTALS = {
  customer: { tagline: 'CUSTOMER SIGN-IN', eyebrow: 'For guests', path: '/customer/login', title: 'Customer sign-in' },
  employee: { tagline: 'STAFF SIGN-IN', eyebrow: 'For the Wendy team', path: '/employee/login', title: 'Staff sign-in' },
  owner: { tagline: 'OWNER SIGN-IN', eyebrow: 'For the owner', path: '/owner/login', title: 'Owner sign-in' },
}

export const ErrorNote = ({ children }) =>
  children ? (
    <p role="alert" className="mb-5 rounded-lg border border-berry/40 bg-berry/5 p-3 text-sm font-medium text-berry">
      {children}
    </p>
  ) : null

export function Field({ id, label, error, hint, ...props }) {
  return (
    <div className="mb-5">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input id={id} name={id} className="field" aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined} {...props} />
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1.5 text-xs opacity-70">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="field-error">
          {error}
        </p>
      )}
    </div>
  )
}

/** One sign-in form used by all three pages. The server decides the role. */
export function LoginPage({ portal }) {
  const copy = PORTALS[portal]
  const { account, apply } = useSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (account && account.role === portal) return <Navigate to={HOME_FOR_ROLE[portal]} replace />

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const data = await api('/auth/login', { method: 'POST', body: { email, password, portal } })
      apply(data)
      navigate(HOME_FOR_ROLE[data.role], { replace: true })
    } catch (err) {
      setError(err.message)
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AreaShell tagline={copy.tagline} title={copy.title}>
      <LoginCard eyebrow={copy.eyebrow} title="Sign in" current={copy.path}>
        {account && (
          <p role="status" className="mb-5 rounded-lg border border-amber bg-citrus/40 p-3 text-sm">
            You are signed in as {account.email} ({account.role}).{' '}
            <Link className="font-semibold underline" to={HOME_FOR_ROLE[account.role]}>
              Go to your page
            </Link>
            , or sign in below with a different account.
          </p>
        )}
        <form onSubmit={submit} aria-label={copy.title}>
          <ErrorNote>{error}</ErrorNote>
          <Field id="login-email" label="Email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Field id="login-password" label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          <button type="submit" className="pill pill-dark w-full" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-5 text-center text-sm">
          <Link className="underline" to="/account/forgot">
            Forgot your password?
          </Link>
        </p>
        {portal === 'customer' ? (
          <p className="mt-5 border-t border-forest/20 pt-5 text-center text-sm">
            New here?{' '}
            <Link className="font-semibold underline" to="/customer/register">
              Create an account
            </Link>
            . You can also{' '}
            <a className="underline" href="/#book">
              request a table without one
            </a>
            .
          </p>
        ) : (
          <p className="mt-5 border-t border-forest/20 pt-5 text-center text-xs opacity-75">
            {portal === 'employee' ? 'Staff accounts are created by the owner, who sends you a link to choose your password.' : 'Owner accounts are set up on the server, not here.'}
          </p>
        )}
      </LoginCard>
    </AreaShell>
  )
}

export function RegisterPage() {
  const { account, apply } = useSession()
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '' })
  const [errors, setErrors] = useState({})
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (name) => (e) => {
    setForm((f) => ({ ...f, [name]: e.target.value }))
    setErrors(({ [name]: _, ...rest }) => rest)
  }

  if (account?.role === 'customer') return <Navigate to="/customer" replace />

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    const found = {}
    if (form.full_name.trim().length < 2) found.full_name = 'Please enter your name.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(form.email.trim())) found.email = 'Enter a valid email address.'
    if (form.phone.trim() && !/^\+\d[\d\s().-]{6,}$/.test(form.phone.trim())) found.phone = 'Start with your country code, for example +977 98XXXXXXXX.'
    if (form.password.length < 12) found.password = 'Use at least 12 characters.'
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    setFailure('')
    try {
      apply(await api('/auth/register', { method: 'POST', body: { full_name: form.full_name.trim(), email: form.email.trim(), phone: form.phone.trim() || null, password: form.password } }))
      navigate('/customer', { replace: true })
    } catch (err) {
      if (Object.keys(err.fields || {}).length) setErrors(err.fields)
      else setFailure(`Your account was not created. ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AreaShell tagline="CREATE AN ACCOUNT" title="Create an account">
      <LoginCard eyebrow="For guests" title="Create an account" current="/customer/login">
        <form onSubmit={submit} noValidate>
          <ErrorNote>{failure}</ErrorNote>
          <Field id="full_name" label="Full name" autoComplete="name" maxLength={120} value={form.full_name} onChange={set('full_name')} error={errors.full_name} />
          <Field id="email" label="Email" type="email" autoComplete="email" maxLength={254} value={form.email} onChange={set('email')} error={errors.email} />
          <Field id="phone" label="Phone (optional)" type="tel" autoComplete="tel" maxLength={32} placeholder="+977 98XXXXXXXX" value={form.phone} onChange={set('phone')} error={errors.phone} hint="With country code. Used to fill in your table requests." />
          <Field id="password" label="Password" type="password" autoComplete="new-password" maxLength={256} value={form.password} onChange={set('password')} error={errors.password} hint="At least 12 characters." />
          <button type="submit" className="pill pill-dark w-full" disabled={busy}>
            {busy ? 'Creating your account…' : 'Create account'}
          </button>
        </form>
        <p className="mt-4 text-xs leading-[1.7] opacity-75">
          We keep your name, email and phone so you can see your table requests and so the team can reach you about them.
          They are not used for marketing.
        </p>
        <p className="mt-5 border-t border-forest/20 pt-5 text-center text-sm">
          Already have an account?{' '}
          <Link className="font-semibold underline" to="/customer/login">
            Sign in
          </Link>
        </p>
      </LoginCard>
    </AreaShell>
  )
}

export function ForgotPage() {
  const [config, setConfig] = useState(undefined) // undefined = loading, null = failed
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/auth/config')
      .then(setConfig)
      .catch(() => setConfig(null))
  }, [])

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      setResult(await api('/auth/password-reset/request', { method: 'POST', body: { email } }))
    } catch (err) {
      setError(`Nothing was sent. ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  const unavailable = (
    <div role="status" className="rounded-lg border border-amber bg-citrus/40 p-4 text-sm leading-[1.7]">
      <strong>Password reset by email is not set up yet.</strong> Nothing can be sent from here. Please contact the shop on{' '}
      <a className="font-semibold underline" href={BUSINESS.phoneHref}>
        {BUSINESS.phoneDisplay}
      </a>
      . Staff should ask the owner for a new setup link.
    </div>
  )

  return (
    <AreaShell tagline="FORGOT PASSWORD" title="Forgot password">
      <LoginCard eyebrow="Account help" title="Forgot password" current="">
        {config === undefined && <p role="status">Checking…</p>}
        {config === null && <ErrorNote>We couldn’t reach the server. Please try again in a moment.</ErrorNote>}
        {config && !config.password_reset_by_email && unavailable}
        {config?.password_reset_by_email && result && (result.email_delivery ? <p role="status" className="rounded-lg bg-citrus/50 p-4 text-sm leading-[1.7]">{result.message}</p> : unavailable)}
        {config?.password_reset_by_email && !result && (
          <form onSubmit={submit}>
            <ErrorNote>{error}</ErrorNote>
            <p className="mb-5 text-sm">Enter your account email and we’ll send a link to choose a new password.</p>
            <Field id="forgot-email" label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            <button type="submit" className="pill pill-dark w-full" disabled={busy}>
              {busy ? 'Sending…' : 'Send reset link'}
            </button>
          </form>
        )}
      </LoginCard>
    </AreaShell>
  )
}

/** Choose a password from an emailed reset link or a staff setup link. */
export function ResetPage() {
  // The token arrives in the URL fragment (#token=...), which is never sent to
  // any server. It is read once and then removed from the address bar.
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '')
  useEffect(() => {
    if (token) window.history.replaceState(null, '', window.location.pathname)
  }, [token])
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    if (password.length < 12) return setError('Use at least 12 characters.')
    if (password !== repeat) return setError('The two passwords do not match.')
    setBusy(true)
    setError('')
    try {
      await api('/auth/password-reset/confirm', { method: 'POST', body: { token, new_password: password } })
      setDone(true)
    } catch (err) {
      setError(err.fields?.new_password || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AreaShell tagline="CHOOSE A PASSWORD" title="Choose a password">
      <LoginCard eyebrow="Account help" title="Choose a password" current="">
        {!token && <ErrorNote>This link is incomplete. Please open the full link you were sent.</ErrorNote>}
        {done && (
          <div role="status" className="rounded-lg bg-citrus/50 p-4 text-sm leading-[1.7]">
            <strong>Your password has been saved.</strong> You were signed out everywhere; sign in again from the links below.
          </div>
        )}
        {token && !done && (
          <form onSubmit={submit}>
            <ErrorNote>{error}</ErrorNote>
            <Field id="new-password" label="New password" type="password" autoComplete="new-password" maxLength={256} required value={password} onChange={(e) => setPassword(e.target.value)} hint="At least 12 characters." />
            <Field id="repeat-password" label="Repeat password" type="password" autoComplete="new-password" maxLength={256} required value={repeat} onChange={(e) => setRepeat(e.target.value)} />
            <button type="submit" className="pill pill-dark w-full" disabled={busy}>
              {busy ? 'Saving…' : 'Save password'}
            </button>
          </form>
        )}
      </LoginCard>
    </AreaShell>
  )
}
