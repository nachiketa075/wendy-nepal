# Asset and source manifest

Last checked: 10 October 2026.

**Permission status in one line:** none of the photographs below have a confirmed reuse licence. They are
guest or listing photos that are publicly viewable; public availability is not permission. All four are
**flagged for owner approval before the site is published**. The owner should either obtain permission from
the photographer/platform or replace them with the shop's own photos.

## Photographs used on the site

Files live in `frontend/public/images/`. Each has a `.webp` (displayed) and a `.jpg` (opened at full size from
the lightbox). Nothing was upscaled, cropped in the file, or had a watermark removed.

| File | Shown as | Pixel size | Retrieved from | Listing page | Permission | Notes |
|---|---|---|---|---|---|---|
| `wendy-fruit-yogurt-bowl` (+ `-640.webp` small variant) | Hero; gallery "Food & drinks" | 1024×1365 | `https://images.happycow.net/venues/1024/15/31/hcmp153127_772936.jpeg` | [HappyCow](https://www.happycow.net/reviews/wendy-juice-shop-nepal-153127) | **Unconfirmed – needs approval** | Guest photo. Faint HappyCow watermark in the centre is preserved. Credited "Guest photo via HappyCow". |
| `wendy-interior-chalkboard-menu` | Our story; gallery "Inside" and "Menu board" | 1024×768 | `https://images.happycow.net/venues/1024/15/31/hcmp153127_1993271.jpeg` | [HappyCow](https://www.happycow.net/reviews/wendy-juice-shop-nepal-153127) | **Unconfirmed – needs approval** | Guest photo, date unknown. HappyCow watermark preserved. Shows prices of unknown date; the lightbox says so. |
| `wendy-historical-fruit-counter` | Gallery "From the archive" – "An earlier chapter at Wendy." | 500×400 | `https://dynamic-media-cdn.tripadvisor.com/media/photo-o/16/e0/21/91/wendy-juice-shop.jpg?h=400&s=1&w=500` | [Tripadvisor](https://www.tripadvisor.com/Restaurant_Review-g293891-d10452354-Reviews-Wendy_Juice_Shop-Pokhara_Gandaki_Zone_Western_Region.html) | **Unconfirmed – needs approval** | Historical photo; labelled as such, never as the current shopfront. Shows two identifiable people – the owner should confirm they are happy to appear. Low resolution, so only shown small. |
| `wendy-exterior-evening` | Gallery "Outside" and "From the archive" – "Lights on at dusk." | 553×367 | `https://1033609670.rsc.cdn77.org/rests/small/w550/h367/339_507918183.jpg` | [Restaurant Guru](https://restaurantguru.com/Wendy-juice-shop-Pokhara/menu) | **Unconfirmed – needs approval** | Sign reads "Wendy Juice & Fruit Shop". Undated; labelled as possibly not the current look. Low resolution, so only shown small. |

All four came from the same three image URLs the original demo used, plus the one extra Restaurant Guru
listing photo. No provided originals were found in the project folder (it was empty).

## Looked at and deliberately not used

| Source | What it is | Why it is not on the site |
|---|---|---|
| `https://menu02.restaurantguru.com/m8/menu-Wendy-juice-shop-rjq.jpg` | Menu photo filed under Wendy on Restaurant Guru | It is the printed menu of a **different restaurant** ("Vegan Way: Vegetarian & Vegan Restaurant"), wrongly attached to Wendy's listing. Nothing from it was used. |
| `https://menu02.restaurantguru.com/m8/Wendy-juice-shop-Cafe-menu-wnq.jpg` | Whiteboard titled "Our services" (bus tickets, flights, trekking, laundry) | Not a food menu, cannot be confirmed as Wendy's, and it shows a Wi‑Fi password. Not used. |
| Tripadvisor photo pages `i576145419`, `i576145473`, `i292913126`, `i593105986` | Additional guest photos | **Not retrieved.** Tripadvisor returned HTTP 403 to automated requests and the block was not bypassed. Source links are kept here for the owner to review by hand. |
| HappyCow listing page | Further guest photos | **Not retrieved.** The page is behind bot protection; only the two direct image URLs given in the brief were downloaded. |
| Facebook page | Shop's own photos | **Not retrieved** (login wall). The best source of approved, current photos – ask the owner. |

## Text sources

| Content | Source | Status |
|---|---|---|
| Name, address, phone, email | Project brief | Used as given; owner to confirm. |
| "Reported in public listings" menu items | Project brief (compiled from Google, Tripadvisor, HappyCow, Restaurant Guru) | Shown with a "Reported in public listings" tag. |
| "Seen on the menu board in a guest photo" items and their wording | Read directly from `wendy-interior-chalkboard-menu` | Only clearly legible text was transcribed. Prices on the board were **not** used. |
| Hero, story, ribbon and section copy | Reference site `wendy-juice-pokhara.adored-berry-9896.chatgpt.site` (fetched and inspected) | Reused. |
| Guest-feedback themes | Project brief | Presented as a summary, explicitly not a quotation. No ratings, counts, reviewer names or dates are shown. |
| Fonts: Playfair Display, DM Sans | Google Fonts (SIL Open Font License) | Loaded from Google's CDN, as on the reference site. |

## Adding or replacing photos

1. Put the new file in `frontend/public/images/` with a descriptive name, at its real size (do not upscale).
2. Add an entry to `frontend/src/lib/gallery.js` with its true `width`/`height`, tags, caption, alt text and credit.
3. Record it in the table above with its source and permission status.
