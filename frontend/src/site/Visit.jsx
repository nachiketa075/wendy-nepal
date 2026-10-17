import { BUSINESS, LOGO_URL } from '../lib/business.js'
import { photoById, photoSrc, photoSrcSet } from '../lib/gallery.js'
import { Brand, ExternalLink, Reveal, SafeImage } from './ui.jsx'

const label = 'text-[11px] uppercase tracking-[2px] text-citrus'
const exterior = photoById('exterior-signboard')
const outline = 'pill border-cream/60 text-cream hover:!text-forest'

export function Visit() {
  return (
    <section id="visit" className="section grid gap-[35px] bg-forest text-cream md:grid-cols-[1.1fr_1fr] md:gap-[8%]">
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
        <div className="mt-5 flex flex-wrap gap-3">
          <ExternalLink href={BUSINESS.mapsUrl} className="pill pill-yellow">
            Get directions
          </ExternalLink>
          <a href={BUSINESS.phoneHref} className={outline}>
            Call us
          </a>
          <ExternalLink href={BUSINESS.whatsappUrl} className={outline}>
            WhatsApp
          </ExternalLink>
        </div>
        <figure className="relative mt-10 max-w-[560px]">
          <SafeImage
            src={photoSrc(exterior, 720)}
            srcSet={photoSrcSet(exterior)}
            sizes="(min-width: 768px) 40vw, 88vw"
            width={exterior.width}
            height={exterior.height}
            loading="lazy"
            alt={exterior.alt}
            className="aspect-[4/3] w-full rounded-[28px_28px_28px_120px] object-cover"
          />
          <figcaption className="absolute bottom-5 right-5 rotate-2 rounded-[10px] bg-cream px-[18px] py-[9px] text-xs text-forest">{exterior.caption}</figcaption>
        </figure>
      </Reveal>
      <Reveal className="pt-2">
        <div className="border-b border-white/20 py-5">
          <span className={label}>Find us</span>
          <address className="my-3 text-base not-italic md:text-lg">
            {BUSINESS.addressLines[0]}
            <br />
            {BUSINESS.addressLines[1]}
          </address>
          <p className="mb-3 text-sm opacity-80">We share a signboard with Nepali Cottage Guest House.</p>
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
          <p className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <a className="underline" href={BUSINESS.phoneHref}>
              Call
            </a>
            <ExternalLink href={BUSINESS.whatsappUrl} className="underline">
              Message on WhatsApp
            </ExternalLink>
            <ExternalLink href={BUSINESS.facebookUrl} className="underline">
              Facebook
            </ExternalLink>
          </p>
        </div>
        <div className="border-b border-white/20 py-5">
          <span className={label}>Planning a visit?</span>
          <p className="my-3 text-base md:text-lg">
            Call for today’s opening hours.
            <br />
            <small className="text-xs opacity-70">We’d rather tell you ourselves than list times that may have changed.</small>
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
        <div className="flex items-center gap-5">
          <SafeImage src={LOGO_URL} width="482" height="482" loading="lazy" alt="Wendy Juice Shop logo" className="h-[92px] w-[92px] shrink-0" />
          <Brand tagline="FRESH FRUIT. HAPPY PEOPLE." />
        </div>
        <p className="font-display text-[17px] italic md:text-[21px]">With love, from Pokhara.</p>
        <address className="text-xs not-italic leading-[1.8]">
          {BUSINESS.name} · {BUSINESS.addressLines.join(', ')}
          <br />
          <a className="underline" href={BUSINESS.phoneHref}>
            {BUSINESS.phoneDisplay}
          </a>{' '}
          ·{' '}
          <ExternalLink href={BUSINESS.whatsappUrl} className="underline">
            WhatsApp
          </ExternalLink>{' '}
          ·{' '}
          <a className="underline" href={`mailto:${BUSINESS.email}`}>
            {BUSINESS.email}
          </a>
        </address>
      </div>
      <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-5 text-[11px] leading-[1.8]">
        <p className="opacity-75">
          Photos and menu supplied by Wendy Juice Shop. Find us on{' '}
          <ExternalLink href={BUSINESS.facebookUrl} className="underline">
            Facebook
          </ExternalLink>
          .
        </p>
      </div>
    </footer>
  )
}
