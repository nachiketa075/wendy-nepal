import { useCallback, useEffect, useRef, useState } from 'react'
import { GALLERY_FILTERS, PHOTOS, photoSrc } from '../lib/gallery.js'
import { SOURCES } from '../lib/business.js'
import { ExternalLink, Reveal, SafeImage } from './ui.jsx'

export default function Gallery() {
  const [filter, setFilter] = useState('all')
  const [openIndex, setOpenIndex] = useState(null)
  const photos = PHOTOS.filter((p) => filter === 'all' || p.tags.includes(filter))

  return (
    <section id="gallery" className="section">
      <Reveal className="mb-[25px] md:mb-[37px] md:flex md:items-end md:justify-between md:gap-10">
        <div>
          <p className="eyebrow">Little moments, big flavour</p>
          <h2 className="h2">
            A taste of <em>Wendy.</em>
          </h2>
        </div>
        <ExternalLink href={SOURCES.tripadvisor} className="textlink mt-5 inline-block md:mt-0">
          Explore guest photos
        </ExternalLink>
      </Reveal>

      <div role="group" aria-label="Gallery filters" className="mb-[30px] flex flex-wrap gap-[7px] md:gap-[10px]">
        {GALLERY_FILTERS.filter((f) => f.id === 'all' || PHOTOS.some((p) => p.tags.includes(f.id))).map((f) => (
          <button key={f.id} type="button" className="chip" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
            {f.label}
          </button>
        ))}
      </div>

      <ul className="grid grid-cols-2 gap-[13px] md:gap-[22px] lg:grid-cols-4">
        {photos.map((photo, index) => (
          <li key={`${filter}-${photo.id}`} className="appear">
            <figure>
              <button
                type="button"
                onClick={() => setOpenIndex(index)}
                aria-label={`View photo: ${photo.caption}`}
                className="group block h-[190px] w-full overflow-hidden rounded-[5px] bg-[#c8cbb3] sm:h-[260px] lg:h-[300px]"
              >
                <SafeImage
                  src={photoSrc(photo)}
                  width={photo.width}
                  height={photo.height}
                  loading="lazy"
                  alt={photo.alt}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                />
              </button>
              <figcaption className="pt-3 font-display text-[17px] italic leading-snug md:pt-4 md:text-xl">
                {photo.caption}
                <span className="mt-1 block font-sans text-[11px] not-italic opacity-65">{photo.credit}</span>
              </figcaption>
            </figure>
          </li>
        ))}
      </ul>

      <p className="mt-6 max-w-3xl text-xs opacity-75">
        These are the photos of Wendy we could source with a traceable origin. They were taken by guests and listing
        sites, and are shown with credit while the shop arranges its own.
      </p>

      {openIndex !== null && photos[openIndex] && (
        <Lightbox photos={photos} index={openIndex} onIndex={setOpenIndex} onClose={() => setOpenIndex(null)} />
      )}
    </section>
  )
}

function Lightbox({ photos, index, onIndex, onClose }) {
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const [zoomed, setZoomed] = useState(false)
  const photo = photos[index]
  const many = photos.length > 1

  const step = useCallback(
    (delta) => {
      setZoomed(false)
      onIndex((index + delta + photos.length) % photos.length)
    },
    [index, photos.length, onIndex],
  )

  // Move focus in, lock page scroll, and hand focus back on close.
  useEffect(() => {
    const previous = document.activeElement
    closeRef.current?.focus()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
      previous?.focus?.()
    }
  }, [])

  const onKeyDown = (event) => {
    if (event.key === 'Escape') onClose()
    else if (event.key === 'ArrowRight' && many) step(1)
    else if (event.key === 'ArrowLeft' && many) step(-1)
    else if (event.key === 'Tab') {
      const focusable = dialogRef.current.querySelectorAll('button, a[href]')
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
  }

  const control = 'rounded-full border border-cream/50 px-4 py-2 text-sm font-semibold text-cream transition-colors hover:bg-cream hover:text-forest'

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={`Photo ${index + 1} of ${photos.length}: ${photo.caption}`}
      onKeyDown={onKeyDown}
      onClick={(e) => e.target === e.currentTarget && onClose()}
      className="fixed inset-0 z-50 flex flex-col bg-[#0c2219]/95 p-4 text-cream md:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs uppercase tracking-[2px]" aria-hidden="true">
          {index + 1} / {photos.length}
        </p>
        <div className="flex flex-wrap gap-2">
          {photo.zoomable && (
            <button type="button" className={control} aria-pressed={zoomed} onClick={() => setZoomed((z) => !z)}>
              {zoomed ? 'Fit to screen' : 'Zoom in to read'}
            </button>
          )}
          <a className={control} href={photoSrc(photo, 'jpg')} target="_blank" rel="noopener noreferrer">
            Open full size<span className="sr-only"> (opens in a new tab)</span>
          </a>
          <button ref={closeRef} type="button" className={control} onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      <div
        className={`my-4 min-h-0 flex-1 ${zoomed ? 'overflow-auto' : 'flex items-center justify-center overflow-hidden'}`}
        onClick={(e) => e.target === e.currentTarget && onClose()}
        tabIndex={zoomed ? 0 : undefined}
        aria-label={zoomed ? 'Zoomed photo, scroll to move around' : undefined}
      >
        <img
          key={photo.id}
          src={photoSrc(photo)}
          alt={photo.alt}
          width={photo.width}
          height={photo.height}
          style={zoomed ? { width: photo.width * 2, maxWidth: 'none', height: 'auto' } : { maxWidth: `min(100%, ${photo.width}px)` }}
          className={zoomed ? 'rounded-[5px]' : 'max-h-full w-auto rounded-[5px] object-contain'}
        />
      </div>

      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="font-display text-xl italic md:text-2xl">{photo.caption}</p>
          {photo.note && <p className="mt-1 max-w-2xl text-sm text-citrus">{photo.note}</p>}
          <p className="mt-1 text-xs opacity-75">
            {photo.credit} ·{' '}
            <a className="underline" href={photo.sourceUrl} target="_blank" rel="noopener noreferrer">
              source<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </p>
        </div>
        {many && (
          <div className="flex shrink-0 gap-2">
            <button type="button" className={control} onClick={() => step(-1)} aria-label="Previous photo">
              ←
            </button>
            <button type="button" className={control} onClick={() => step(1)} aria-label="Next photo">
              →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
