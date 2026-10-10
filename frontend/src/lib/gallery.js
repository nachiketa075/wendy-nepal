import { SOURCES } from './business.js'

// Every photo here is listed in docs/ASSET_MANIFEST.md with its source and
// permission status. Sizes are the real pixel sizes so nothing is upscaled.
export const GALLERY_FILTERS = [
  { id: 'all', label: 'Everything' },
  { id: 'food', label: 'Food & drinks' },
  { id: 'interior', label: 'Inside' },
  { id: 'exterior', label: 'Outside' },
  { id: 'menu', label: 'Menu board' },
  { id: 'historical', label: 'From the archive' },
]

export const PHOTOS = [
  {
    id: 'fruit-yogurt-bowl',
    file: 'wendy-fruit-yogurt-bowl',
    width: 1024,
    height: 1365,
    tags: ['food'],
    caption: 'Fresh starts, happy days.',
    alt: 'A white bowl of chopped fresh fruit topped with yogurt and pomegranate seeds on a wooden table at Wendy Juice Shop',
    credit: 'Guest photo via HappyCow',
    sourceUrl: SOURCES.happycow,
  },
  {
    id: 'interior-chalkboard-menu',
    file: 'wendy-interior-chalkboard-menu',
    width: 1024,
    height: 768,
    tags: ['interior', 'menu'],
    caption: 'The chalkboard, the juicer, the cups.',
    alt: 'Inside Wendy Juice Shop: a wood-framed chalkboard menu under a woven lamp, above a counter with a juicer, blender and cups, beside a stone wall',
    note: 'Prices on the board are from an undated guest photo and may not be current. Please ask us for today’s prices.',
    credit: 'Guest photo via HappyCow',
    sourceUrl: SOURCES.happycow,
    zoomable: true,
  },
  {
    id: 'exterior-evening',
    file: 'wendy-exterior-evening',
    width: 553,
    height: 367,
    tags: ['exterior', 'historical'],
    caption: 'Lights on at dusk.',
    alt: 'An evening street view of a small shop signed “Wendy Juice & Fruit Shop”, with a lit fruit counter, a yellow awning and outdoor tables',
    note: 'An undated photo from a public listing. The shop may look different today.',
    credit: 'Listing photo via Restaurant Guru',
    sourceUrl: SOURCES.restaurantguru,
  },
  {
    id: 'historical-fruit-counter',
    file: 'wendy-historical-fruit-counter',
    width: 500,
    height: 400,
    tags: ['historical'],
    caption: 'An earlier chapter at Wendy.',
    alt: 'An older photograph of Wendy Juice Shop’s original fruit counter, with shelves of pineapples, apples and pomegranates and two people at the counter',
    note: 'A historical photo, not the current shopfront.',
    credit: 'Guest photo via Tripadvisor',
    sourceUrl: SOURCES.tripadvisor,
  },
]

export const photoSrc = (photo, ext = 'webp') => `/images/${photo.file}.${ext}`
