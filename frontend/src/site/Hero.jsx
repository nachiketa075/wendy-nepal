import { SafeImage } from './ui.jsx'

export function Hero() {
  return (
    <section id="home" className="grid md:min-h-[680px] md:grid-cols-2">
      <div className="px-[6%] pb-[25px] pt-10 md:px-[10%] md:pt-[45px] xl:px-[12%] xl:pb-[35px] xl:pt-[62px]">
        <p className="eyebrow">Fresh fruit. Good company. Pokhara.</p>
        <h1 className="mb-6 text-[clamp(52px,6.7vw,100px)]">
          A little
          <br />
          freshness.
          <br />
          <em className="whitespace-nowrap">A lot of joy.</em>
        </h1>
        <p className="mb-7 max-w-[370px] leading-[1.8]">
          Fresh juices, colourful bowls and a slower kind of morning. Your little Lakeside stop for something good.
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <a className="pill pill-yellow" href="#menu">
            Explore the menu
          </a>
          <a className="pill" href="#book">
            Book a table
          </a>
        </div>
        <div className="mt-[22px] flex items-center justify-between text-xs leading-[1.6] md:mt-10">
          <span>
            Made for slow mornings
            <br />
            &amp; sunny afternoons.
          </span>
          <span
            aria-hidden="true"
            className="flex h-[65px] w-[65px] rotate-[13deg] items-center justify-center rounded-full border border-forest text-center text-[10px] tracking-[2px] md:h-20 md:w-20"
          >
            FRESH
            <br />
            EVERY DAY
          </span>
        </div>
      </div>
      <div className="relative mx-[6%] mb-[25px] h-[420px] overflow-hidden rounded-[160px_160px_6px_6px] bg-[#c8cbb3] md:my-[23px] md:ml-0 md:mr-6 md:h-auto md:rounded-[180px_180px_8px_8px]">
        <SafeImage
          src="/images/wendy-fruit-yogurt-bowl.webp"
          srcSet="/images/wendy-fruit-yogurt-bowl-640.webp 640w, /images/wendy-fruit-yogurt-bowl.webp 1024w"
          sizes="(min-width: 768px) 50vw, 88vw"
          width="1024"
          height="1365"
          fetchpriority="high"
          alt="A bowl of fresh fruit with yogurt and pomegranate seeds served at Wendy Juice Shop in Pokhara"
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div className="absolute bottom-[25px] left-[25px] -rotate-[4deg] rounded-[5px] bg-cream px-[25px] py-[15px] font-display text-2xl">
          A taste of Lakeside
          <span className="block font-sans text-[11px] uppercase leading-[1.5] tracking-[2px]">Pokhara, Nepal</span>
        </div>
      </div>
    </section>
  )
}

const HIGHLIGHTS = ['Freshly squeezed', 'Bowls of happiness', 'Good coffee', 'Lakeside living']

export function Ribbon() {
  return (
    <ul
      aria-label="Menu highlights"
      className="flex items-center justify-around gap-[9px] bg-citrus px-[15px] py-[15px] text-[11px] font-semibold md:gap-5 md:px-[3%] md:py-[19px] md:text-sm"
    >
      {HIGHLIGHTS.map((text, i) => (
        <li key={text} className={`flex items-center gap-[9px] md:gap-5 ${i === 3 ? 'hidden sm:flex' : ''}`}>
          <span>{text}</span>
          <span aria-hidden="true" className={`text-[25px] font-normal leading-none ${i === 2 ? 'hidden sm:inline' : ''}`}>
            ✳
          </span>
        </li>
      ))}
    </ul>
  )
}
