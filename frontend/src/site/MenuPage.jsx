import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { BUSINESS, MENU_PDF_URL, formatPrice } from '../lib/business.js'
import { photoById, photoSrc, photoSrcSet } from '../lib/gallery.js'
import { loadMenu } from '../lib/menuService.js'
import Header from './Header.jsx'
import { SafeImage } from './ui.jsx'
import { Footer } from './Visit.jsx'

const heroPhoto = photoById('breakfast-plate-and-drinks')

const addonText = (addon) => `${addon.label} – ${addon.prefix || ''}${formatPrice(addon.price)}${addon.unit ? ` ${addon.unit}` : ''}`

function matches(item, category, query) {
  if (!query) return true
  const haystack = [item.name, item.description, category.name, ...(item.addons || []).map((a) => a.label)]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return query.split(/\s+/).every((word) => haystack.includes(word))
}

/** The full menu, on its own page at /menu. */
export default function MenuPage() {
  const [state, setState] = useState({ status: 'loading', categories: [] })
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const filter = params.get('category') || 'all'
  const setFilter = (slug) => setParams(slug === 'all' ? {} : { category: slug }, { replace: true, preventScrollReset: true })

  useEffect(() => {
    document.title = 'Menu · Wendy Juice Shop'
    window.scrollTo({ top: 0, behavior: 'instant' })
    const controller = new AbortController()
    loadMenu({ signal: controller.signal })
      .then((data) => setState({ status: 'ready', ...data }))
      .catch((err) => err.name !== 'AbortError' && setState({ status: 'error', categories: [] }))
    return () => controller.abort()
  }, [])

  const categories = useMemo(() => state.categories.filter((c) => c.items.length > 0), [state.categories])
  const query = search.trim().toLowerCase()
  const known = filter === 'all' || categories.some((c) => c.slug === filter)
  const shown = useMemo(
    () =>
      categories
        .filter((c) => !known || filter === 'all' || c.slug === filter)
        .map((c) => ({ ...c, items: c.items.filter((item) => matches(item, c, query)) }))
        .filter((c) => c.items.length > 0),
    [categories, filter, known, query],
  )
  const count = shown.reduce((n, c) => n + c.items.length, 0)
  const filterName = categories.find((c) => c.slug === filter)?.name
  const reset = () => {
    setFilter('all')
    setSearch('')
  }

  return (
    <div className="shell">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-cream focus:p-3">
        Skip to content
      </a>
      <Header />
      <main id="main">
        <section className="grid bg-forest text-cream md:grid-cols-[1.2fr_1fr]">
          <div className="px-[6%] py-14 md:py-20 md:pl-[10%] lg:py-24">
            <p className="kicker text-citrus">Wendy Juice Shop · Lakeside</p>
            <h1 className="text-[clamp(52px,6.2vw,96px)]">
              The <em className="text-citrus">menu.</em>
            </h1>
            <p className="mt-6 max-w-[420px] leading-[1.85] opacity-90">
              Pressed, blended and plated to order. Take your time, and ask us what’s especially good today.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/#book" className="pill pill-yellow">
                Book a table
              </Link>
              <a href={BUSINESS.phoneHref} className="pill border-cream/60 text-cream hover:!text-forest">
                Call us
              </a>
            </div>
          </div>
          <div className="relative min-h-[260px] md:min-h-[440px]">
            <SafeImage
              src={photoSrc(heroPhoto)}
              srcSet={photoSrcSet(heroPhoto)}
              sizes="(min-width: 768px) 45vw, 100vw"
              width={heroPhoto.width}
              height={heroPhoto.height}
              fetchpriority="high"
              alt={heroPhoto.alt}
              className="absolute inset-0 h-full w-full object-cover md:rounded-tl-[220px]"
            />
          </div>
        </section>

        {state.status === 'loading' && (
          <p role="status" className="section text-sm">
            Loading the menu…
          </p>
        )}

        {state.status === 'error' && (
          <div className="section">
            <p role="alert" className="rounded-lg border border-line bg-sage p-6 text-sm">
              We couldn’t load the menu just now. Please refresh, or call us on{' '}
              <a className="font-semibold underline" href={BUSINESS.phoneHref}>
                {BUSINESS.phoneDisplay}
              </a>
              .
            </p>
          </div>
        )}

        {state.status === 'ready' && (
          <>
            <div className="sticky top-[90px] z-20 border-b border-line bg-cream/95 px-[6%] py-4 backdrop-blur md:top-[100px]">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-6">
                <div className="relative w-full shrink-0 lg:w-[280px]">
                  <label htmlFor="menu-search" className="sr-only">
                    Search the menu
                  </label>
                  <input
                    id="menu-search"
                    type="search"
                    className="field !rounded-[30px] !py-2.5 pr-16 !text-sm"
                    placeholder="Search the menu"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    autoComplete="off"
                  />
                  {search && (
                    <button type="button" className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-semibold underline" onClick={() => setSearch('')}>
                      Clear
                    </button>
                  )}
                </div>
                <div role="group" aria-label="Menu categories" className="-mx-[6vw] flex gap-2 overflow-x-auto px-[6vw] pb-1 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0 lg:pb-0">
                  <button type="button" className="chip shrink-0" aria-pressed={!known || filter === 'all'} onClick={() => setFilter('all')}>
                    All
                  </button>
                  {categories.map((c) => (
                    <button key={c.id} type="button" className="chip shrink-0 whitespace-nowrap" aria-pressed={filter === c.slug} onClick={() => setFilter(c.slug)}>
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="section !pt-12">
              <p role="status" aria-live="polite" className="sr-only">
                {count} menu {count === 1 ? 'item' : 'items'} shown.
              </p>

              {shown.length === 0 && (
                <div className="mx-auto max-w-xl rounded-[20px] bg-sage p-10 text-center">
                  <h2 className="text-[30px] tracking-[-0.6px]">Nothing on the menu matches that.</h2>
                  <p className="my-4 text-sm">
                    {query ? `No dishes match “${search.trim()}”` : 'No dishes'}
                    {filterName ? ` in ${filterName}` : ''}. Try another word, or see everything.
                  </p>
                  <button type="button" className="pill" onClick={reset}>
                    Show the whole menu
                  </button>
                </div>
              )}

              <div className="mx-auto max-w-[1180px]">
                {shown.map((category) => (
                  <section key={`${filter}-${category.id}`} aria-labelledby={`cat-${category.slug}`} className="appear mb-16 scroll-mt-[240px] last:mb-0 md:mb-20">
                    <div className="mb-8 text-center">
                      <span aria-hidden="true" className="text-xl text-forest/50">
                        ✳
                      </span>
                      <h2 id={`cat-${category.slug}`} className="mt-1 text-[36px] tracking-[-1px] md:text-[48px]">
                        {category.name}
                      </h2>
                      {category.notes?.map((note) => (
                        <p key={note.label} className="mt-3 inline-block rounded-full border border-forest/30 px-4 py-1 text-xs font-semibold tracking-[0.5px]">
                          {note.label} {note.prefix || ''}
                          {formatPrice(note.price)}
                        </p>
                      ))}
                    </div>
                    <ul className="grid gap-x-16 gap-y-7 md:grid-cols-2">
                      {category.items.map((item) => (
                        <li key={item.id} className={item.is_available ? '' : 'opacity-55'}>
                          <div className="flex items-end">
                            <h3 className="font-display text-[20px] font-medium leading-snug tracking-[-0.3px] md:text-[23px]">{item.name}</h3>
                            <span aria-hidden="true" className="leader" />
                            {item.price_npr !== null && <span className="shrink-0 whitespace-nowrap text-[15px] font-semibold">{formatPrice(item.price_npr)}</span>}
                          </div>
                          {item.description && <p className="mt-1.5 max-w-[46ch] text-[13.5px] italic leading-[1.65] opacity-80">{item.description}</p>}
                          {item.addons?.map((addon) => (
                            <p key={addon.label} className="mt-1.5 text-[12.5px] font-semibold uppercase tracking-[1px]">
                              {addonText(addon)}
                            </p>
                          ))}
                          {!item.is_available && <p className="mt-1.5 text-xs font-semibold uppercase tracking-[1.5px]">Not available right now</p>}
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>

              <p className="mx-auto mt-16 max-w-[1180px] border-t border-line pt-6 text-center text-xs opacity-75">
                Prices are in Nepalese rupees. Ask us about today’s availability.{' '}
                <a className="underline" href={MENU_PDF_URL} target="_blank" rel="noopener noreferrer">
                  Printed menu (PDF)<span className="sr-only"> (opens in a new tab)</span>
                </a>
              </p>
            </div>

            <section className="bg-citrus px-[6%] py-12 text-center md:py-16">
              <h2 className="text-[34px] tracking-[-1px] md:text-[48px]">
                Found a favourite? <em>Come and try it.</em>
              </h2>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <Link to="/#book" className="pill pill-dark">
                  Book a table
                </Link>
                <a href={BUSINESS.whatsappUrl} target="_blank" rel="noopener noreferrer" className="pill hover:!bg-cream">
                  WhatsApp us<span className="sr-only"> (opens in a new tab)</span>
                </a>
              </div>
            </section>
          </>
        )}
      </main>
      <Footer />
    </div>
  )
}
