# Asset and source manifest

Last updated: 12 October 2026.

Everything shown on the site now comes from material **supplied by the shop on 10 October 2026**: thirteen
photographs (sent as WhatsApp JPEGs) and the printed menu `CM.pdf`. The earlier third-party photos were
removed from the site.

## Supplied photographs (all 13 are in the gallery)

- **Originals**, byte-for-byte as supplied: `frontend/public/images/original/<name>.jpg`
  (opened by "Open full size" in the gallery lightbox).
- **Display copies**: `frontend/public/images/<name>.webp` (full size) and `<name>-720.webp` (longest side 720 px).
  Nothing was upscaled, retouched or cropped in the files.

| Supplied file (`WhatsApp Image 2026-10-10 at …`) | Saved as | Pixels | What it shows | Used in |
|---|---|---|---|---|
| `17.11.48 (3).jpeg` | `wendy-fruit-bowl-close-up` | 1200×1600 | Fruit bowl from above | Hero, gallery (Food) |
| `17.11.49 (2).jpeg` | `wendy-breakfast-plate-and-drinks` | 1200×1600 | Breakfast plate, fruit bowl, juice | Menu heading, gallery (Food) |
| `17.11.49 (1).jpeg` | `wendy-exterior-signboard` | 1600×1200 | Building and signboard from the street | Visit us, gallery (Outside) |
| `17.11.50.jpeg` | `wendy-interior-stone-seating-area` | 1600×1200 | Seating area with guests reading and chatting | Our story, gallery (Inside) |
| `17.11.49.jpeg` | `wendy-group-waving-in-seating-area` | 1600×1200 | Large group waving in the seating area | Gallery (Guests, Inside) |
| `17.11.50 (3).jpeg` | `wendy-group-cheering-in-seating-area` | 1600×1200 | Same group, hands raised | Gallery (Guests, Inside) |
| `17.11.47.jpeg` | `wendy-guests-toasting-with-tea` | 1600×1200 | Five guests raising glasses of milk tea | Gallery (Guests) |
| `17.11.48 (1).jpeg` | `wendy-guest-with-juice-and-fruit-bowl` | 1200×1600 | A guest with juice and a fruit bowl | Gallery (Guests, Food) |
| `17.11.48 (2).jpeg` | `wendy-guest-with-juice-and-fruit-bowl-closer` | 1200×1600 | Same guest, closer | Gallery (Guests, Food) |
| `17.11.48 (4).jpeg` | `wendy-guest-holding-fruit-yogurt-bowl` | 1200×1600 | A guest holding a fruit and yogurt bowl | Gallery (Guests, Food) |
| `17.11.48.jpeg` | `wendy-guests-selfie-at-window-table` | 1600×1200 | Two guests taking a selfie | Gallery (Guests) |
| `17.11.50 (1).jpeg` | `wendy-guests-with-lassi-evening` | 1600×1200 | Two guests raising glasses in the evening | Gallery (Guests) |
| `17.11.50 (2).jpeg` | `wendy-guests-sharing-breakfast` | 1600×1200 | Four guests at breakfast | Gallery (Guests, Food) |

**Provenance:** supplied directly by the shop for this website. **Still to confirm:** eleven of the thirteen
show identifiable people (including children in the seating-area photo). The owner should confirm those guests
are happy to appear on a public website; see `OWNER_CONFIRMATION.md`. Alt text and captions describe people
without naming them.

The brief expected `17.11.49` and `17.11.50 (3)` to be interior shots. They do show the seating area, but both
are group photos of guests, so they are tagged "Guests" as well as "Inside". `17.11.50` is the main interior view.

## Menu and logo

| Asset | Location | Source |
|---|---|---|
| Printed menu (3 pages) | `frontend/public/menu/wendy-juice-shop-menu.pdf` | `CM.pdf`, unchanged (5.0 MB) |
| Menu data shown on the site | `frontend/src/data/menuFromPdf.js` | Transcribed from `CM.pdf`; each category and item records its page |
| Logo | `frontend/public/images/wendy-juice-shop-logo.webp` (and `.png`) | The 482×482 logo image embedded in `CM.pdf` page 1, extracted with its transparency |

The logo is used in the footer and on the sign-in pages. The header keeps the existing "wendy" wordmark, which
is part of the approved design.

## Removed in this update

These four third-party photos had no confirmed reuse permission and are no longer in the project folder. They
remain in the repository's earlier commit history.

| Former file | Came from |
|---|---|
| `wendy-fruit-yogurt-bowl` | HappyCow guest photo |
| `wendy-interior-chalkboard-menu` | HappyCow guest photo |
| `wendy-historical-fruit-counter` | Tripadvisor guest photo |
| `wendy-exterior-evening` | Restaurant Guru listing photo |

## Other sources

| Content | Source |
|---|---|
| Phone, WhatsApp, address, email, Facebook | Owner brief; the phone number also appears on the shop's signboard in the supplied photo |
| "We share a signboard with Nepali Cottage Guest House" | Read from the supplied exterior photo |
| Hero, story and section copy | The approved reference design |
| Guest-feedback themes | Summary from the original brief; shown as a summary, not a quotation |
| Fonts (Playfair Display, DM Sans) | Google Fonts, SIL Open Font License |

## Adding or replacing photos

1. Put the untouched file in `frontend/public/images/original/` with a descriptive name.
2. Create `<name>.webp` and `<name>-720.webp` display copies beside the others (do not upscale).
3. Add an entry to `frontend/src/lib/gallery.js` with the true width and height, tags, caption and alt text.
4. Record it in the table above.
