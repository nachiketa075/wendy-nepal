import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import Booking from './Booking.jsx'
import Feedback from './Feedback.jsx'
import Gallery from './Gallery.jsx'
import Header from './Header.jsx'
import { Hero, Ribbon } from './Hero.jsx'
import MenuSection from './MenuSection.jsx'
import Story from './Story.jsx'
import { Footer, Visit } from './Visit.jsx'

/** Scrolls to the section named in the URL (#story, #book…), including when arriving from another page. */
function useHashScroll() {
  const { hash, key } = useLocation()
  useEffect(() => {
    if (!hash) return
    const go = () => document.getElementById(hash.slice(1))?.scrollIntoView()
    go()
    // Again once late-loading sections above have taken their height.
    const timer = setTimeout(go, 450)
    return () => clearTimeout(timer)
  }, [hash, key])
}

export default function SitePage() {
  useHashScroll()
  useEffect(() => {
    document.title = 'Wendy Juice Shop · A little freshness in Pokhara'
  }, [])
  return (
    <div className="shell">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-cream focus:p-3">
        Skip to content
      </a>
      <Header />
      <main id="main">
        <Hero />
        <Ribbon />
        <MenuSection />
        <Story />
        <Gallery />
        <Feedback />
        <Booking />
        <Visit />
      </main>
      <Footer />
    </div>
  )
}
