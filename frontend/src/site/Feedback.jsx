import { SOURCES } from '../lib/business.js'
import { ExternalLink, Reveal } from './ui.jsx'

const THEMES = ['Fresh fruit', 'Smoothie bowls', 'Friendly staff', 'A relaxed atmosphere', 'Vegan options']

const PLATFORMS = [
  ['Tripadvisor', SOURCES.tripadvisor],
  ['Google Maps', SOURCES.google],
  ['HappyCow', SOURCES.happycow],
  ['Facebook', SOURCES.facebook],
]

export default function Feedback() {
  return (
    <section id="feedback" className="section !pt-0" aria-labelledby="feedback-title">
      <Reveal className="grid gap-8 rounded-[20px] bg-citrus p-[27px] md:grid-cols-[1.1fr_1fr] md:gap-[8%] md:p-[50px]">
        <div>
          <span aria-hidden="true" className="text-[40px] leading-none">
            ✳
          </span>
          <p className="eyebrow !mb-5 mt-2 !text-[10px]">What guests love</p>
          <h2 id="feedback-title" className="text-[32px] leading-[1.25] tracking-[-1px] md:text-[42px] md:leading-[1.15]">
            Fresh fruit.
            <br />
            Friendly faces.
            <br />
            A moment to unwind.
          </h2>
        </div>
        <div className="self-end">
          <p className="text-sm leading-[1.8]">
            These are the themes that keep coming up when guests write about Wendy on public review sites. This is our
            summary, not a quotation.
          </p>
          <ul className="my-5 flex flex-wrap gap-2" aria-label="Themes guests mention">
            {THEMES.map((theme) => (
              <li key={theme} className="rounded-[30px] border border-forest/40 px-4 py-1.5 text-[13px]">
                {theme}
              </li>
            ))}
          </ul>
          <p className="text-sm leading-[1.8]">Read what guests actually wrote, in their own words:</p>
          <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-3">
            {PLATFORMS.map(([name, url]) => (
              <li key={name}>
                <ExternalLink href={url} className="textlink">
                  {name}
                </ExternalLink>
              </li>
            ))}
          </ul>
        </div>
      </Reveal>
    </section>
  )
}
