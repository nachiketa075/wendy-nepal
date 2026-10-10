import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { BUSINESS } from '../lib/business.js'
import { Reveal } from './ui.jsx'

const SOURCE_LABELS = {
  listing: 'Reported in public listings',
  menu_photo: 'Seen on the menu board in a guest photo',
}

const formatNpr = (value) => `NPR ${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

export default function MenuSection() {
  const [state, setState] = useState({ status: 'loading', categories: [] })
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    const controller = new AbortController()
    api('/menu', { signal: controller.signal })
      .then((data) => setState({ status: 'ready', categories: data.categories }))
      .catch((err) => err.name !== 'AbortError' && setState({ status: 'error', categories: [] }))
    return () => controller.abort()
  }, [])

  const categories = state.categories.filter((c) => c.items.length > 0)
  const shown = categories.filter((c) => filter === 'all' || c.slug === filter)
  const items = shown.flatMap((c) => c.items.map((item) => ({ ...item, tagline: c.tagline || c.name })))
  const hasPrices = items.some((i) => i.price_npr !== null)

  return (
    <section id="menu" className="section">
      <Reveal className="mb-[25px] md:mb-[37px] md:flex md:items-end md:justify-between md:gap-10">
        <div>
          <p className="eyebrow">Pick your happy</p>
          <h2 className="h2">
            Something fresh.
            <br />
            Something <em>you.</em>
          </h2>
        </div>
        <p className="mt-5 text-sm leading-[1.8] md:mt-0">
          From your first sip to the last spoonful.
          <br />
          Find a favourite, or try a little something new.
        </p>
      </Reveal>

      {state.status === 'loading' && (
        <p role="status" className="py-10 text-sm">
          Loading the menu…
        </p>
      )}

      {state.status === 'error' && (
        <p role="alert" className="rounded-lg border border-line bg-sage p-6 text-sm">
          We couldn’t load the menu just now. Please refresh, or call us on{' '}
          <a className="font-semibold underline" href={BUSINESS.phoneHref}>
            {BUSINESS.phoneDisplay}
          </a>{' '}
          and we’ll tell you what’s fresh today.
        </p>
      )}

      {state.status === 'ready' && (
        <>
          <div role="group" aria-label="Menu categories" className="mb-[30px] flex flex-wrap gap-[7px] md:gap-[10px]">
            <button type="button" className="chip" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
              All
            </button>
            {categories.map((c) => (
              <button key={c.id} type="button" className="chip" aria-pressed={filter === c.slug} onClick={() => setFilter(c.slug)}>
                {c.name}
              </button>
            ))}
          </div>

          <ul aria-live="polite" className="grid grid-cols-1 border-l border-t border-line sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <li
                key={`${filter}-${item.id}`}
                className={`appear border-b border-r border-line px-[18px] py-5 md:px-7 md:py-[27px] ${item.is_available ? '' : 'opacity-60'}`}
              >
                <span className="text-[10px] uppercase tracking-[2px] opacity-70">{item.tagline}</span>
                <div className="my-3 flex items-baseline justify-between gap-4">
                  <h3 className="text-[23px] tracking-[-0.6px] md:text-[26px]">{item.name}</h3>
                  {item.price_npr !== null && (
                    <span className="shrink-0 whitespace-nowrap text-sm font-semibold">{formatNpr(item.price_npr)}</span>
                  )}
                </div>
                {item.description && <p className="max-w-[340px] text-[13px] leading-[1.7] md:text-sm">{item.description}</p>}
                {!item.is_available && <p className="mt-2 text-xs font-semibold uppercase tracking-[1.5px]">Not available right now</p>}
                {SOURCE_LABELS[item.source] && (
                  <p className="mt-3 text-[11px] opacity-65">
                    <span aria-hidden="true">{item.source === 'listing' ? '● ' : '○ '}</span>
                    {SOURCE_LABELS[item.source]}
                  </p>
                )}
              </li>
            ))}
          </ul>
          {items.length === 0 && <p className="py-8 text-sm">Nothing listed here yet.</p>}

          <p className="mt-5 max-w-3xl text-xs opacity-75">
            This menu is gathered from public listings and a guest photo of the menu board, so it may not match today’s
            menu exactly.{' '}
            {hasPrices
              ? 'Prices are shown only where the shop has confirmed them, in Nepalese rupees (NPR).'
              : 'Prices are not shown until the shop confirms them.'}{' '}
            Ask us about today’s availability, prices and vegan options.
          </p>
        </>
      )}
    </section>
  )
}
