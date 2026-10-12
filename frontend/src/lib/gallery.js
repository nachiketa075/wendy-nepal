// The 13 photographs supplied by the shop on 10 Oct 2026. Each is recorded in
// docs/ASSET_MANIFEST.md. Sizes are the real pixel sizes; nothing is upscaled.
// People are described, never named.
export const GALLERY_FILTERS = [
  { id: 'all', label: 'Everything' },
  { id: 'food', label: 'Food & drinks' },
  { id: 'interior', label: 'Inside' },
  { id: 'exterior', label: 'Outside' },
  { id: 'guests', label: 'Guests & moments' },
]

const L = { width: 1600, height: 1200 }
const P = { width: 1200, height: 1600 }

export const PHOTOS = [
  {
    id: 'fruit-bowl-close-up',
    file: 'wendy-fruit-bowl-close-up',
    ...P,
    tags: ['food'],
    caption: 'Fresh starts, happy days.',
    alt: 'A fruit bowl seen from above, topped with apple slices, orange segments, watermelon, pomegranate seeds, raisins and a sprig of mint',
  },
  {
    id: 'breakfast-plate-and-drinks',
    file: 'wendy-breakfast-plate-and-drinks',
    ...P,
    tags: ['food'],
    caption: 'Breakfast, the slow way.',
    alt: 'A breakfast plate with toast, butter, jam and sautéed vegetables beside a fruit bowl, a small bowl of watermelon and a red juice',
  },
  {
    id: 'interior-stone-seating-area',
    file: 'wendy-interior-stone-seating-area',
    ...L,
    tags: ['interior'],
    caption: 'Stone walls, soft seats.',
    alt: 'The seating area at Wendy Juice Shop: stone walls, wooden sofas with grey cushions, woven lamps and guests reading and chatting at their tables',
  },
  {
    id: 'exterior-signboard',
    file: 'wendy-exterior-signboard',
    ...L,
    tags: ['exterior'],
    caption: 'Look for the black sign.',
    alt: 'The stone building of Wendy Juice Shop from the street, with a black signboard reading Nepali Cottage Guest House and Wendy Juice Shop',
  },
  {
    id: 'guest-holding-fruit-yogurt-bowl',
    file: 'wendy-guest-holding-fruit-yogurt-bowl',
    ...P,
    tags: ['guests'],
    caption: 'A bowl worth smiling about.',
    alt: 'A smiling guest on a sofa holding a bowl of fruit and yogurt topped with orange and pomegranate',
  },
  {
    id: 'guests-sharing-breakfast',
    file: 'wendy-guests-sharing-breakfast',
    ...L,
    tags: ['guests'],
    caption: 'Morning light, full table.',
    alt: 'Four guests smiling around a table covered with omelettes, toast, fruit salad and tea in the morning sun',
  },
  {
    id: 'group-waving-in-seating-area',
    file: 'wendy-group-waving-in-seating-area',
    ...L,
    tags: ['guests', 'interior'],
    caption: 'Room for the whole group.',
    alt: 'A large group of guests waving and giving thumbs up from the sofas in the stone-walled seating area',
  },
  {
    id: 'guests-toasting-with-tea',
    file: 'wendy-guests-toasting-with-tea',
    ...L,
    tags: ['guests'],
    caption: 'Cheers to milk tea.',
    alt: 'Five guests at a window table raising glasses of milk tea towards the camera',
  },
  {
    id: 'guest-with-juice-and-fruit-bowl',
    file: 'wendy-guest-with-juice-and-fruit-bowl',
    ...P,
    tags: ['guests'],
    caption: 'Juice first, then the bowl.',
    alt: 'A guest smiling at a window table behind a tall glass of yellow juice and a fruit-topped bowl',
  },
  {
    id: 'guests-with-lassi-evening',
    file: 'wendy-guests-with-lassi-evening',
    ...L,
    tags: ['guests'],
    caption: 'An evening round.',
    alt: 'Two guests on a cushioned bench raising tall glasses of lassi in the evening',
  },
  {
    id: 'guests-selfie-at-window-table',
    file: 'wendy-guests-selfie-at-window-table',
    ...L,
    tags: ['guests'],
    caption: 'One for the album.',
    alt: 'Two guests taking a selfie at a table by the stone wall, with a glass of juice and a fruit bowl',
  },
  {
    id: 'group-cheering-in-seating-area',
    file: 'wendy-group-cheering-in-seating-area',
    ...L,
    tags: ['guests', 'interior'],
    caption: 'Hands up for a good morning.',
    alt: 'A large group of guests cheering with raised hands from the sofas in the seating area',
  },
  {
    id: 'guest-with-juice-and-fruit-bowl-closer',
    file: 'wendy-guest-with-juice-and-fruit-bowl-closer',
    ...P,
    tags: ['guests'],
    caption: 'Fruit, juice, and time to enjoy it.',
    alt: 'A closer view of a smiling guest with a glass of yellow juice and a bowl topped with apple, watermelon, banana and nuts',
  },
]

export const photoById = (id) => PHOTOS.find((p) => p.id === id)
/** Optimised display copy; pass 720 for the smaller variant. */
export const photoSrc = (photo, size) => `/images/${photo.file}${size ? `-${size}` : ''}.webp`
/** The untouched original as supplied. */
export const photoOriginal = (photo) => `/images/original/${photo.file}.jpg`
export const photoSrcSet = (photo) => {
  const small = Math.round((Math.max(photo.width, photo.height) === photo.width ? 720 : (720 * photo.width) / photo.height))
  return `${photoSrc(photo, 720)} ${small}w, ${photoSrc(photo)} ${photo.width}w`
}
