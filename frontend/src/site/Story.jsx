import { photoById, photoSrc, photoSrcSet } from '../lib/gallery.js'
import { Reveal, SafeImage } from './ui.jsx'

const storyPhoto = photoById('interior-stone-seating-area')

export default function Story() {
  return (
    <section id="story" className="section grid items-center gap-9 bg-sage md:grid-cols-2 md:gap-[8%]">
      <Reveal className="relative h-[390px] md:h-[430px] lg:h-[520px]">
        <SafeImage
          src={photoSrc(storyPhoto)}
          srcSet={photoSrcSet(storyPhoto)}
          sizes="(min-width: 768px) 44vw, 88vw"
          width={storyPhoto.width}
          height={storyPhoto.height}
          loading="lazy"
          alt={storyPhoto.alt}
          className="h-full w-full rounded-[5px_5px_150px_5px] object-cover"
        />
        <span className="absolute bottom-5 left-5 -rotate-3 bg-cream px-[18px] py-[9px] text-xs">A little corner of Pokhara.</span>
      </Reveal>
      <Reveal>
        <p className="eyebrow">Rooted in Lakeside</p>
        <h2 className="text-[clamp(35px,3.8vw,55px)]">
          Come for the fruit.
          <br />
          <em>Stay for the feeling.</em>
        </h2>
        <p className="my-[26px] max-w-[440px] leading-[1.85]">
          Some stops become part of the trip. A fresh juice after a lakeside walk. A colourful breakfast before the day
          begins. A quiet table, and time to enjoy it.
        </p>
        <p className="my-[26px] max-w-[440px] leading-[1.85]">
          At Wendy, fresh fruit, comforting favourites and a friendly welcome come together in the heart of Pokhara’s
          Lakeside.
        </p>
        <a className="textlink" href="#book">
          Make yourself at home
        </a>
      </Reveal>
    </section>
  )
}
