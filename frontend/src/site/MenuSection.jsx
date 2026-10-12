import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BUSINESS, formatPrice } from '../lib/business.js'
import { photoById, photoSrc } from '../lib/gallery.js'
import { loadMenu } from '../lib/menuService.js'
import { Reveal, SafeImage } from './ui.jsx'

const highlight = photoById('breakfast-plate-and-drinks')

/** Home-page introduction to the menu. The full list lives on /menu. */
export default function MenuSection() {
  const [state, setState] = useState({ status: 'loading', categories: [] })

  useEffect(() => {
    const controller = new AbortController()
    loadMenu({ signal: controller.signal })
      .then((data) => setState({ status: 'ready', categories: data.categories.filter((c) => c.items.length > 0) }))
      .catch((err) => err.name !== 'AbortError' && setState({ status: 'error', categories: [] }))
    return () => controller.abort()
  }, [])

  return (
    <section id="menu" className="section">
      <div className="grid items-center gap-10 lg:grid-cols-[1fr_auto] lg:gap-[8%]">
        <Reveal>
          <p className="kicker">Pick your happy</p>
          <h2 className="h2">
            Something fresh.
            <br />
            Something <em>you.</em>
          </h2>
          <p className="mt-6 max-w-[440px] leading-[1.85]">
            From your first sip to the last spoonful. Cold-pressed juices, slow breakfasts and bowls built with fruit that
            came in this morning.
          </p>
          <Link className="pill pill-dark mt-7" to="/menu">
            See the full menu <span aria-hidden="true">→</span>
          </Link>
        </Reveal>
        <Reveal className="relative mx-auto h-[340px] w-[260px] lg:mx-0 lg:h-[400px] lg:w-[310px]">
          <SafeImage
            src={photoSrc(highlight, 720)}
            width={highlight.width}
            height={highlight.height}
            loading="lazy"
            alt={highlight.alt}
            className="h-full w-full rounded-[160px_160px_28px_28px] object-cover shadow-[0_30px_60px_-30px_rgba(22,61,45,0.6)]"
          />
          <span className="absolute -left-5 bottom-6 -rotate-3 rounded-[10px] bg-cream px-[18px] py-[9px] text-xs shadow-md">{highlight.caption}</span>
        </Reveal>
      </div>

      {state.status === 'error' && (
        <p role="alert" className="mt-10 rounded-lg border border-line bg-sage p-6 text-sm">
          We couldn’t load the menu just now. Please refresh, or call us on{' '}
          <a className="font-semibold underline" href={BUSINESS.phoneHref}>
            {BUSINESS.phoneDisplay}
          </a>
          .
        </p>
      )}

      {state.status === 'ready' && (
        <Reveal as="ul" aria-label="Menu sections" className="mt-12 grid grid-cols-2 border-l border-t border-line md:mt-16 md:grid-cols-3 xl:grid-cols-4">
          {state.categories.map((category, index) => {
            const from = Math.min(...category.items.filter((i) => i.price_npr !== null).map((i) => Number(i.price_npr)))
            return (
              <li key={category.id} className="border-b border-r border-line">
                <Link
                  to={`/menu?category=${category.slug}`}
                  className="group flex h-full flex-col justify-between gap-6 p-5 transition-colors duration-300 hover:bg-forest hover:text-cream md:p-7"
                >
                  <span className="text-[11px] tracking-[3px] opacity-60">{String(index + 1).padStart(2, '0')}</span>
                  <span>
                    <span className="block font-display text-[22px] leading-tight tracking-[-0.5px] md:text-[28px]">{category.name}</span>
                    <span className="mt-2 flex items-center justify-between gap-3 text-xs opacity-75">
                      <span>
                        {category.items.length} {category.items.length === 1 ? 'choice' : 'choices'}
                        {Number.isFinite(from) ? ` · from ${formatPrice(from)}` : ''}
                      </span>
                      <span aria-hidden="true" className="transition-transform duration-300 group-hover:translate-x-1 group-hover:text-citrus">
                        →
                      </span>
                    </span>
                  </span>
                </Link>
              </li>
            )
          })}
        </Reveal>
      )}
    </section>
  )
}
