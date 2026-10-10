import { BUSINESS, SOURCES } from '../lib/business.js'
import { Brand, ExternalLink, Reveal } from './ui.jsx'

const label = 'text-[11px] uppercase tracking-[2px] text-citrus'

export function Visit() {
  return (
    <section id="visit" className="section grid gap-[35px] bg-forest text-cream md:grid-cols-[1.1fr_1fr] md:gap-[10%]">
      <Reveal>
        <p className="eyebrow">Your next little stop</p>
        <h2 className="text-[clamp(58px,6vw,86px)]">
          See you
          <br />
          in <em className="text-citrus">Lakeside.</em>
        </h2>
        <p className="my-4">
          Step away from the rush.
          <br />
          There’s something fresh waiting for you.
        </p>
        <ExternalLink href={BUSINESS.mapsUrl} className="pill pill-yellow mt-5">
          Get directions
        </ExternalLink>
      </Reveal>
      <Reveal className="pt-2">
        <div className="border-b border-white/20 py-5">
          <span className={label}>Find us</span>
          <address className="my-3 text-base not-italic md:text-lg">
            {BUSINESS.addressLines[0]}
            <br />
            {BUSINESS.addressLines[1]}
          </address>
          <ExternalLink href={BUSINESS.mapsUrl} className="text-sm underline">
            Open in Google Maps
          </ExternalLink>
        </div>
        <div className="border-b border-white/20 py-5">
          <span className={label}>Let’s talk</span>
          <p className="my-3 text-base md:text-lg">
            <a className="hover:underline" href={BUSINESS.phoneHref}>
              {BUSINESS.phoneDisplay}
            </a>
            <br />
            <a className="break-all hover:underline" href={`mailto:${BUSINESS.email}`}>
              {BUSINESS.email}
            </a>
          </p>
        </div>
        <div className="border-b border-white/20 py-5">
          <span className={label}>Planning a visit?</span>
          <p className="my-3 text-base md:text-lg">
            Call for today’s opening hours.
            <br />
            <small className="text-xs opacity-70">Public listings show different times, so we’d rather tell you ourselves.</small>
          </p>
        </div>
      </Reveal>
    </section>
  )
}

export function Footer() {
  return (
    <footer className="px-[6%] py-[35px] md:py-[45px]">
      <div className="flex flex-wrap items-center justify-between gap-6">
        <Brand tagline="FRESH FRUIT. HAPPY PEOPLE." />
        <p className="font-display text-[17px] italic md:text-[21px]">With love, from Pokhara.</p>
        <address className="text-xs not-italic leading-[1.8]">
          {BUSINESS.name} · {BUSINESS.addressLines.join(', ')}
          <br />
          <a className="underline" href={BUSINESS.phoneHref}>
            {BUSINESS.phoneDisplay}
          </a>{' '}
          ·{' '}
          <a className="underline" href={`mailto:${BUSINESS.email}`}>
            {BUSINESS.email}
          </a>
        </address>
      </div>
      <p className="mt-8 border-t border-line pt-5 text-[11px] leading-[1.8] opacity-75">
        Photos: guest and listing photos via{' '}
        <ExternalLink href={SOURCES.happycow} className="underline">
          HappyCow
        </ExternalLink>
        ,{' '}
        <ExternalLink href={SOURCES.tripadvisor} className="underline">
          Tripadvisor
        </ExternalLink>{' '}
        and{' '}
        <ExternalLink href={SOURCES.restaurantguru} className="underline">
          Restaurant Guru
        </ExternalLink>
        , credited to their sources and pending the shop’s approval. Menu details come from public listings and may have
        changed. Find Wendy on{' '}
        <ExternalLink href={SOURCES.facebook} className="underline">
          Facebook
        </ExternalLink>
        .
      </p>
    </footer>
  )
}
