import Booking from './Booking.jsx'
import Feedback from './Feedback.jsx'
import Gallery from './Gallery.jsx'
import Header from './Header.jsx'
import { Hero, Ribbon } from './Hero.jsx'
import MenuSection from './MenuSection.jsx'
import Story from './Story.jsx'
import { Footer, Visit } from './Visit.jsx'

export default function SitePage() {
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
