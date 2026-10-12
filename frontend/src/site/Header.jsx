import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Brand } from './ui.jsx'

const LINKS = [
  ['/menu', 'Menu'],
  ['/#story', 'Our story'],
  ['/#gallery', 'Gallery'],
  ['/#visit', 'Visit us'],
]

export default function Header() {
  const [open, setOpen] = useState(false)

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
        <div className="flex items-center gap-3">
          <Link to="/customer/login" className="hidden text-sm transition-opacity hover:opacity-65 xl:inline">
            Sign in
          </Link>
          <Link to="/#book" className="pill hidden sm:inline-flex">
            Book a table <span aria-hidden="true">↗</span>
          </Link>
          <button
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
        <nav id="mobile-nav" aria-label="Main navigation" className="appear border-t border-line px-[6%] py-3 lg:hidden">
          {[...LINKS, ['/#book', 'Book a table']].map(([href, label]) => (
            <Link key={href} to={href} onClick={() => setOpen(false)} className="block py-3 font-display text-2xl">
              {label}
            </Link>
          ))}
          <Link to="/customer/login" className="block border-t border-line py-3 text-sm">
            Sign in
          </Link>
        </nav>
      )}
    </header>
  )
}
