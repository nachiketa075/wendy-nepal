import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { SIGN_OUT_FAILED } from '../auth/AuthLayout.jsx'
import { useSession } from '../lib/session.jsx'
import { Brand } from './ui.jsx'

const LINKS = [
  ['/menu', 'Menu'],
  ['/#story', 'Our story'],
  ['/#gallery', 'Gallery'],
  ['/#visit', 'Visit us'],
]

const SIGN_IN = [
  ['/customer/login', 'Customer sign in', 'Your table requests'],
  ['/employee/login', 'Staff sign in', 'The team dashboard'],
  ['/owner/login', 'Owner sign in', 'Run the shop'],
]

const ROLE_LABEL = { customer: 'Customer', employee: 'Staff', owner: 'Owner' }

/** Where a signed-in account can go. Only pages that exist for that role. */
function accountLinks(role) {
  if (role === 'customer') {
    return [
      ['/customer', 'My bookings'],
      ['/customer/profile', 'My account'],
    ]
  }
  if (role === 'owner') {
    return [
      ['/owner', 'Owner dashboard'],
      ['/owner/account', 'Account settings'],
    ]
  }
  return [
    ['/employee', 'Staff dashboard'],
    ['/employee/account', 'Account settings'],
  ]
}

/**
 * Sign-in options for visitors, or the account's own pages and Sign out once
 * the server has confirmed a session (useSession). Nothing is shown while that
 * check is still running, so the wrong state never flashes.
 */
export default function Header() {
  const [open, setOpen] = useState(false)
  const menuButton = useRef(null)
  const mobileNav = useRef(null)
  const { account } = useSession()
  const signOut = useSignOut()

  // Close the mobile menu with Escape, or by tapping outside it.
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
        menuButton.current?.focus()
      }
    }
    const onPointer = (event) => {
      if (!mobileNav.current?.contains(event.target) && !menuButton.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-cream/95 backdrop-blur">
      <div className="flex h-[90px] items-center justify-between gap-6 px-[6%] md:h-[100px]">
        <Brand />
        <nav aria-label="Main navigation" className="hidden items-center gap-8 text-sm lg:flex">
          {LINKS.map(([href, label]) => (
            <Link key={href} to={href} className="transition-opacity hover:opacity-65">
              {label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-5">
          <div className="hidden lg:block">
            <AccountMenu account={account} signOut={signOut} />
          </div>
          <Link to="/#book" className="pill hidden sm:inline-flex">
            Book a table <span aria-hidden="true">↗</span>
          </Link>
          <button
            ref={menuButton}
            type="button"
            className="pill !px-4 lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? 'Close' : 'Menu'}
          </button>
        </div>
      </div>
      {open && (
        <nav ref={mobileNav} id="mobile-nav" aria-label="Main navigation" className="appear border-t border-line px-[6%] py-3 lg:hidden">
          {[...LINKS, ['/#book', 'Book a table']].map(([href, label]) => (
            <Link key={href} to={href} onClick={() => setOpen(false)} className="block py-3 font-display text-2xl">
              {label}
            </Link>
          ))}
          <MobileAccount account={account} signOut={signOut} onNavigate={() => setOpen(false)} />
        </nav>
      )}
      <p role="status" className="sr-only">
        {signOut.announcement}
      </p>
    </header>
  )
}

/** Sign out from the public site, keeping track of progress and failure. */
function useSignOut() {
  const { signOut } = useSession()
  const [state, setState] = useState({ busy: false, failed: false, announcement: '' })
  const run = async () => {
    if (state.busy) return false
    setState({ busy: true, failed: false, announcement: '' })
    const ok = await signOut()
    setState({ busy: false, failed: !ok, announcement: ok ? 'You are signed out.' : '' })
    return ok
  }
  return Object.assign(run, state)
}

/** Desktop: a disclosure button with a small panel of links (Escape and outside clicks close it). */
function AccountMenu({ account, signOut }) {
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  const button = useRef(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
        button.current?.focus()
      }
    }
    const onPointer = (event) => {
      if (!box.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  // Arrow keys move between the panel's links and buttons.
  const onPanelKey = (event) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    const items = [...box.current.querySelectorAll('[data-menu-item]')]
    const index = items.indexOf(document.activeElement)
    const next = event.key === 'ArrowDown' ? (index + 1) % items.length : (index - 1 + items.length) % items.length
    items[next]?.focus()
    event.preventDefault()
  }
  const openWithKeys = (event) => {
    if (event.key !== 'ArrowDown') return
    event.preventDefault()
    setOpen(true)
    requestAnimationFrame(() => box.current?.querySelector('[data-menu-item]')?.focus())
  }
  // Tabbing out of the menu closes it (clicks outside are handled above).
  const onBlur = (event) => {
    if (event.relatedTarget && !box.current?.contains(event.relatedTarget)) setOpen(false)
  }

  if (account === undefined) return <span aria-hidden="true" className="inline-block w-[84px]" />

  const signedIn = Boolean(account)
  const firstName = signedIn ? account.full_name.split(' ')[0] : ''
  const item = 'block rounded-[14px] px-4 py-3 text-sm transition-colors hover:bg-sage focus-visible:bg-sage'

  return (
    <div ref={box} className="relative" onBlur={onBlur} onKeyDown={open ? onPanelKey : undefined}>
      <button
        ref={button}
        type="button"
        className="flex items-center gap-2 text-sm transition-opacity hover:opacity-65"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={signedIn ? `Account menu for ${account.full_name} (${ROLE_LABEL[account.role]})` : undefined}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={openWithKeys}
      >
        {signedIn && (
          <span aria-hidden="true" className="grid h-8 w-8 place-items-center rounded-full bg-forest text-xs font-semibold text-cream">
            {firstName.charAt(0).toUpperCase()}
          </span>
        )}
        <span>{signedIn ? firstName : 'Sign in'}</span>
        <span aria-hidden="true" className={`text-[10px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>
      {open && (
        <div id={panelId} className="appear absolute right-0 top-full z-40 mt-4 w-[272px] rounded-[20px] border border-line bg-cream p-2 shadow-[0_18px_40px_-22px_rgba(22,61,45,0.55)]">
          {signedIn ? (
            <>
              <div className="border-b border-line px-4 pb-3 pt-2">
                <p className="truncate text-sm font-semibold">{account.full_name}</p>
                <p className="truncate text-xs opacity-70">
                  {ROLE_LABEL[account.role]} · {account.email}
                </p>
              </div>
              <ul className="py-1">
                {accountLinks(account.role).map(([href, label]) => (
                  <li key={href}>
                    <Link data-menu-item to={href} className={item} onClick={() => setOpen(false)}>
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
              <div className="border-t border-line pt-1">
                <button
                  data-menu-item
                  type="button"
                  className={`${item} w-full text-left font-semibold`}
                  disabled={signOut.busy}
                  onClick={async () => {
                    if (await signOut()) {
                      setOpen(false)
                      button.current?.focus() // the same button, now offering Sign in
                    }
                  }}
                >
                  {signOut.busy ? 'Signing out…' : 'Sign out'}
                </button>
                {signOut.failed && (
                  <p role="alert" className="px-4 pb-2 text-xs font-medium text-berry">
                    {SIGN_OUT_FAILED}
                  </p>
                )}
              </div>
            </>
          ) : (
            <ul>
              {SIGN_IN.map(([href, label, hint]) => (
                <li key={href}>
                  <Link data-menu-item to={href} className={item} onClick={() => setOpen(false)}>
                    <span className="block font-semibold">{label}</span>
                    <span className="block text-xs opacity-65">{hint}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

/** Phones and tablets: the same choices at the bottom of the menu panel. */
function MobileAccount({ account, signOut, onNavigate }) {
  if (account === undefined) return null
  const link = 'block py-2.5 text-base'
  if (!account) {
    return (
      <div className="mt-2 border-t border-line pt-4">
        <p className="field-label !mb-1">Sign in</p>
        {SIGN_IN.map(([href, label]) => (
          <Link key={href} to={href} onClick={onNavigate} className={link}>
            {label}
          </Link>
        ))}
      </div>
    )
  }
  return (
    <div className="mt-2 border-t border-line pt-4">
      <p className="field-label !mb-1">
        {ROLE_LABEL[account.role]} · {account.full_name}
      </p>
      {accountLinks(account.role).map(([href, label]) => (
        <Link key={href} to={href} onClick={onNavigate} className={link}>
          {label}
        </Link>
      ))}
      <button
        type="button"
        className={`${link} w-full text-left font-semibold`}
        disabled={signOut.busy}
        onClick={async () => {
          if (await signOut()) onNavigate()
        }}
      >
        {signOut.busy ? 'Signing out…' : 'Sign out'}
      </button>
      {signOut.failed && (
        <p role="alert" className="pb-2 text-sm font-medium text-berry">
          {SIGN_OUT_FAILED}
        </p>
      )}
    </div>
  )
}
