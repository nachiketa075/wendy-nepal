import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setCsrfToken } from './api.js'

const SessionContext = createContext(null)

export const HOME_FOR_ROLE = { customer: '/customer', employee: '/employee', owner: '/owner' }

/**
 * Holds who is signed in, as reported by the server (GET /api/auth/me).
 * `account` is undefined while checking, null when signed out. The role and
 * permissions here only decide what to show; the server enforces them.
 */
export function SessionProvider({ children }) {
  const [account, setAccount] = useState(undefined)

  const apply = useCallback((data) => {
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

  const value = useMemo(
    () => ({
      account,
      apply,
      refresh,
      can: (permission) => account?.role === 'owner' || (account?.role === 'employee' && account.permissions.includes(permission)),
      signOut: async () => {
        try {
          await api('/auth/logout', { method: 'POST' })
        } catch {
          // The session is cleared locally either way.
        }
        apply(null)
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
