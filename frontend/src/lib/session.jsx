import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, setCsrfToken } from './api.js'

const SessionContext = createContext(null)

export const HOME_FOR_ROLE = { customer: '/customer', employee: '/employee', owner: '/owner' }

// How often a returning tab may re-check the session with the server.
const RECHECK_MS = 60 * 1000

/**
 * Holds who is signed in, as reported by the server (GET /api/auth/me).
 * `account` is undefined while checking, null when signed out. The role and
 * permissions here only decide what to show; the server enforces them.
 *
 * There is one session cookie per browser, so exactly one account (and one
 * role) at a time: signing in on another portal replaces it. Nothing about the
 * session is kept in browser storage.
 */
export function SessionProvider({ children }) {
  const [account, setAccount] = useState(undefined)
  const lastCheck = useRef(0)

  const apply = useCallback((data) => {
    lastCheck.current = Date.now()
    setCsrfToken(data?.csrf_token ?? null)
    setAccount(data ?? null)
  }, [])

  const refresh = useCallback(
    () =>
      api('/auth/me')
        .then(apply)
        .catch(() => apply(null)),
    [apply],
  )

  useEffect(() => {
    refresh()
  }, [refresh])

  // When someone comes back to the tab, ask the server again (at most once a
  // minute), so a session that expired or was revoked meanwhile stops showing
  // as signed in. Only a definite 401 signs out; a network hiccup changes nothing.
  useEffect(() => {
    const recheck = () => {
      if (document.visibilityState !== 'visible' || Date.now() - lastCheck.current < RECHECK_MS) return
      lastCheck.current = Date.now()
      api('/auth/me')
        .then(apply)
        .catch((err) => err.status === 401 && apply(null))
    }
    window.addEventListener('focus', recheck)
    document.addEventListener('visibilitychange', recheck)
    return () => {
      window.removeEventListener('focus', recheck)
      document.removeEventListener('visibilitychange', recheck)
    }
  }, [apply])

  const value = useMemo(
    () => ({
      account,
      apply,
      refresh,
      can: (permission) => account?.role === 'owner' || (account?.role === 'employee' && account.permissions.includes(permission)),
      // Returns true once the server has ended the session (or it had already
      // ended). On a network or server error the session may still be valid,
      // so nothing changes here and false is returned.
      signOut: async () => {
        try {
          await api('/auth/logout', { method: 'POST' })
        } catch (err) {
          if (err.status !== 401) return false
        }
        apply(null)
        return true
      },
      // Pass any API error here: an expired or revoked session signs the user out.
      handleAuthError: (err) => {
        if (err?.status === 401) {
          apply(null)
          return true
        }
        return false
      },
    }),
    [account, apply, refresh],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export const useSession = () => useContext(SessionContext)
