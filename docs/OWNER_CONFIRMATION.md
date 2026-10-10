# Details that need the owner's confirmation

Nothing below is presented on the site as a confirmed fact. Each item says what the site does in the meantime.

## Must be settled before the site goes live

| # | What we need | Why | What the site does until then |
|---|---|---|---|
| 1 | **Booking windows, group sizes, notice period and how far ahead guests may book** | The seeded values are placeholders invented for the demo (every day 8:00 AM–6:00 PM, 1–8 guests, 2 hours' notice, 30 days ahead, half-hour steps). They were *not* taken from any listing. | In production, the booking form stays closed until the owner reviews them in **Owner dashboard → Booking settings**, ticks the confirmation box and saves. |
| 2 | **Permission for the four photographs** (see `ASSET_MANIFEST.md`) | They are guest/listing photos with no confirmed licence. One shows two identifiable people. | Shown with source credit. Replace or clear them before publishing. |
| 3 | **Opening hours** | Listings disagree: Google 6:00 AM–10:00 PM, Tripadvisor 6:00 AM–9:00 PM, HappyCow 6:30 AM–8:00 PM, and a Trip.com listing found during checking shows 8:00 AM–9:00 PM. | The site says "Call for today's opening hours." No hours are displayed. |
| 4 | **The menu: items, wording and prices** | Items come from public listings and from an undated guest photo of the chalkboard. The board showed prices, but their date is unknown so none were entered. | Every item carries a small source tag and no price. Edit in **Owner dashboard → Menu**; a price appears (as NPR) only once the owner types one in. |
| 5 | **Contact details**: +977 985-6031094, kushwaha_3@hotmail.com, Pahari Marga / 15th Street, Lakeside, Pokhara 33700 | Taken from the brief. One listing gives the street differently. | Shown as given. |

## Could not be verified, so left off the site

| Item | Reported value | What was found when checking (10 Oct 2026) |
|---|---|---|
| Google rating | 4.7/5 from 292 reviews | Could not be checked automatically. Not shown. |
| Tripadvisor rating | 4.9/5 from 176 reviews | Tripadvisor blocked automated access. Not shown. |
| Family-business history | "Since 1986, renovated in 2022" | Not confirmed by any source reached; one listing summary says fruit and juice have been sold "since 1985". The story section therefore gives no dates. |
| Price range | Rs 500–1,000 (Google) | A general range, not menu pricing. Not shown. |

If the owner confirms ratings, the site should show them with the platform name and the date they were checked.

## Decisions for the owner

- **Who gets a dashboard login?** Accounts are created from the command line (see README); there is no sign-up page.
- **How will guests be told the outcome?** The site sends no email, SMS or WhatsApp. Staff contact the guest themselves and record the result in the dashboard. Automatic messages would need a provider account and extra work.
- **How long should guest contact details be kept?** Nothing is deleted automatically at present. The booking form tells guests they can ask for removal.
- **Should table capacity be tracked?** It is not. The dashboard never stops the owner confirming more requests than there are tables; checking availability is the owner's job, and the site never claims real-time availability.
