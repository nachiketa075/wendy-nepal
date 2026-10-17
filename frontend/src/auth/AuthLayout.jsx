import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LOGO_URL } from '../lib/business.js'
import { useSession } from '../lib/session.jsx'
import { Brand, SafeImage } from '../site/ui.jsx'

const AREAS = [
  ['/customer/login', 'Customer'],
  ['/employee/login', 'Staff'],
  ['/owner/login', 'Owner'],
]

export const SIGN_OUT_FAILED = 'Could not sign out. Check your connection and try again.'

/** Ends the session on the server; says so if that did not work. */
export function SignOutButton({ className = 'pill !py-2' }) {
  const { signOut } = useSession()
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const click = async () => {
    if (busy) return
    setBusy(true)
    setFailed(false)
    const ok = await signOut()
    setBusy(false) // harmless if the area has already unmounted
    setFailed(!ok)
  }
  return (
    <>
      <button type="button" className={className} disabled={busy} onClick={click}>
        {busy ? 'Signing out…' : 'Sign out'}
      </button>
      {failed && (
        <span role="alert" className="text-sm font-medium text-berry">
          {SIGN_OUT_FAILED}
        </span>
      )}
    </>
  )
}

/** Shared frame for the three sign-in pages and the signed-in areas. */
export function AreaShell({ tagline, title, right, banner, children }) {
  useEffect(() => {
    document.title = `${title} · Wendy Juice Shop`
  }, [title])
  return (
    <div className="shell flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-[6%] py-5">
        <Brand tagline={tagline} href="/" />
        <div className="flex items-center gap-4 text-sm">{right}</div>
      </header>
      {banner}
      <main className="flex-1 px-[6%] py-10">{children}</main>
      <footer className="border-t border-line px-[6%] py-5 text-xs">
        <Link className="underline" to="/">
          ← Back to the website
        </Link>
      </footer>
    </div>
  )
}

/** Card with the logo, the heading, and links to the other two sign-in pages. */
export function LoginCard({ eyebrow, title, current, children }) {
  return (
    <div className="mx-auto max-w-md">
      <div className="rounded-[20px] bg-sage p-7 md:p-8">
        <SafeImage src={LOGO_URL} width="482" height="482" alt="Wendy Juice Shop logo" className="mx-auto mb-5 h-[96px] w-[96px]" />
        <p className="eyebrow !mb-3 text-center">{eyebrow}</p>
        <h1 className="mb-6 text-center text-[40px]">{title}</h1>
        {children}
      </div>
      <nav aria-label="Other sign-in pages" className="mt-5 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm">
        {AREAS.filter(([path]) => path !== current).map(([path, label]) => (
          <Link key={path} className="underline" to={path}>
            {label} sign-in
          </Link>
        ))}
      </nav>
    </div>
  )
}
