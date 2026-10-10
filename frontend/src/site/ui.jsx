import { useEffect, useRef, useState } from 'react'

/** Image that degrades to a quiet placeholder instead of a broken icon. */
export function SafeImage({ className = '', alt, ...props }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <div
        role="img"
        aria-label={`${alt} (photo unavailable)`}
        className={`flex items-center justify-center bg-[#c8cbb3] p-4 text-center text-xs uppercase tracking-[2px] text-forest/70 ${className}`}
      >
        Photo unavailable
      </div>
    )
  }
  return <img alt={alt} className={className} onError={() => setFailed(true)} {...props} />
}

/** Fades content in once as it scrolls into view. No-op with reduced motion (see index.css). */
export function Reveal({ as: Tag = 'div', className = '', children, ...props }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node || !('IntersectionObserver' in window)) {
      setVisible(true)
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.12 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <Tag ref={ref} className={`reveal ${visible ? 'is-visible' : ''} ${className}`} {...props}>
      {children}
    </Tag>
  )
}

export function Brand({ tagline = 'JUICE SHOP · POKHARA', href = '/#home' }) {
  return (
    <a href={href} aria-label="Wendy Juice Shop home" className="font-display text-[41px] font-semibold leading-[0.8] tracking-[-3px] md:text-[49px]">
      wendy
      <span className="mt-[5px] block font-sans text-[10px] font-semibold leading-[2.8] tracking-[2px]">{tagline}</span>
    </a>
  )
}

export function ExternalLink({ href, className = '', children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  )
}
