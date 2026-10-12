import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { LoginCard } from '../auth/AuthLayout.jsx'
import { api, setCsrfToken } from '../lib/api.js'
import { PREVIEW_ENABLED } from '../lib/preview.js'
import { Brand } from '../site/ui.jsx'
import BookingsPanel from './BookingsPanel.jsx'
import MenuPanel from './MenuPanel.jsx'
import SettingsPanel from './SettingsPanel.jsx'

const TABS = [
  ['bookings', 'Table requests'],
  ['settings', 'Booking settings'],
  ['menu', 'Menu'],
]

// Design preview only (fictional data, nothing saved). The tab and its code are
// left out entirely unless the development preview switch is on.
const TeamPanel = PREVIEW_ENABLED ? lazy(() => import('../preview/TeamPanel.jsx')) : null
if (PREVIEW_ENABLED) TABS.push(['team', 'Team (preview)'])

export default function OwnerApp() {
  const [session, setSession] = useState(undefined) // undefined = checking, null = signed out
  const [tab, setTab] = useState('bookings')
  // This component serves /owner and /owner/login with the one real session.
  const onLoginPage = useLocation().pathname.replace(/\/+$/, '') === '/owner/login'

  useEffect(() => {
    document.title = 'Owner · Wendy Juice Shop'
    api('/auth/me')
      .then((data) => {
        setCsrfToken(data.csrf_token)
        setSession(data)
      })
      .catch(() => setSession(null))
  }, [])

  // Panels call this with any error; an expired session sends the owner back to sign-in.
  const onAuthError = useCallback((err) => {
    if (err?.status === 401) {
      setCsrfToken(null)
      setSession(null)
      return true
    }
    return false
  }, [])

  const signOut = async () => {
    try {
      await api('/auth/logout', { method: 'POST' })
    } catch {
      // The session is cleared locally either way.
    }
    setCsrfToken(null)
    setSession(null)
  }

  return (
    <div className="shell min-h-screen">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-[6%] py-5">
        <Brand tagline={session ? 'OWNER DASHBOARD' : 'OWNER SIGN-IN'} href="/" />
        {session && (
          <div className="flex items-center gap-4 text-sm">
            <span className="hidden sm:inline">{session.email}</span>
            <button type="button" className="pill !py-2" onClick={signOut}>
              Sign out
            </button>
          </div>
        )}
      </header>

      <main className="px-[6%] py-10">
        {session === undefined && <p role="status">Checking your session…</p>}
        {session === null && !onLoginPage && <Navigate to="/owner/login" replace />}
        {session && onLoginPage && <Navigate to="/owner" replace />}
        {session === null && onLoginPage && (
          <Login
            onSignedIn={(data) => {
              setCsrfToken(data.csrf_token)
              setSession(data)
            }}
          />
        )}
        {session && (
          <>
            <div role="group" aria-label="Dashboard sections" className="mb-8 flex flex-wrap gap-2">
              {TABS.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={tab === id}
                  className="chip"
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div>
              {tab === 'bookings' && <BookingsPanel onAuthError={onAuthError} />}
              {tab === 'settings' && <SettingsPanel onAuthError={onAuthError} />}
              {tab === 'menu' && <MenuPanel onAuthError={onAuthError} />}
              {tab === 'team' && TeamPanel && (
                <Suspense fallback={<p role="status">Loading…</p>}>
                  <TeamPanel />
                </Suspense>
              )}
            </div>
          </>
        )}
      </main>
      <footer className="border-t border-line px-[6%] py-5 text-xs">
        <Link className="underline" to="/">
          ← Back to the website
        </Link>
      </footer>
    </div>
  )
}

function Login({ onSignedIn }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      onSignedIn(await api('/auth/login', { method: 'POST', body: { email, password } }))
    } catch (err) {
      setError(err.message)
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <LoginCard eyebrow="For the owner" title="Sign in" current="/owner/login">
      <form onSubmit={submit} aria-label="Owner sign-in">
        {error && (
          <p role="alert" className="mb-5 rounded-lg border border-berry/40 bg-berry/5 p-3 text-sm font-medium text-berry">
            {error}
          </p>
        )}
        <label className="field-label" htmlFor="login-email">
          Email
        </label>
        <input id="login-email" type="email" className="field mb-5" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <label className="field-label" htmlFor="login-password">
          Password
        </label>
        <input
          id="login-password"
          type="password"
          className="field mb-6"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit" className="pill pill-dark w-full" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </LoginCard>
  )
}
