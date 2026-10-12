# Details that need the owner's confirmation

Last updated: 12 October 2026.

## Confirmed since the first version

- **Phone and WhatsApp:** +977 985-6031094 (also on the shop's signboard).
- **Menu and prices:** the printed menu `CM.pdf` is now the public menu.
- **Photographs:** thirteen photos supplied by the shop replace the earlier third-party ones.

## Questions about the printed menu

The website shows the menu **exactly as printed**. Nothing below was corrected or guessed. Please tell us what
each should say.

| # | Where | What is printed | Question |
|---|---|---|---|
| 1 | Brunch → **Vegan Porridge** (Rs. 450) | Description reads "Sourdough Toast, Avocado, Cherry Tomatoes" | That describes toast, not porridge. What is the right description (or the right dish name)? |
| 2 | **Rice Bowl** section | Lists "Vegan Buddha Bowl Rs. 600" and "Chicken Buddha Bowl Rs. 680", identical to the Buddha Bowl section | What are the actual rice bowls and their prices? |
| 3 | Brunch → **Cheese Frittata** (Rs. 500) | Description ends "…fresh vegetables, sausages" | Does the frittata include sausages? Its name suggests a vegetarian dish. |
| 4 | Smoothie → **Matcha Muse** | "Match Powder" | Should this read "Matcha Powder"? |
| 5 | Smoothie → **Banananut Smoothie** | "Coco Powder" | Cocoa powder or coconut powder? |
| 6 | Brunch → **Vegan Breakfast** | "fruit salad" appears twice in the description | Remove the repeat? |
| 7 | Fresh Juice | "Banana lassi 180" is listed under Fresh Juice; Lassi/Milkshake also has "Banana 180" | Is this intended? |
| 8 | Brunch → **Oatmeal Pancake** | Described as "creamy banana oats made with milk…" | Is this a pancake or an oat bowl? |

No dietary or allergen labels (vegan, gluten-free, nut-free and so on) have been added, because the menu does
not state them beyond the dish names.

## Still needed before the site goes live

| # | What we need | What the site does until then |
|---|---|---|
| 1 | **Booking windows, group sizes, notice period, how far ahead.** The seeded values are placeholders (every day 8:00 AM–6:00 PM, 1–8 guests, 2 hours' notice, 30 days ahead). | In production the booking form stays closed until the owner confirms them in Owner dashboard → Booking settings. |
| 2 | **Opening hours.** Public listings disagree. | "Call for today's opening hours." No hours are shown. |
| 3 | **Consent from the guests in the photos.** Eleven of the thirteen photos show identifiable people, and one includes children. | All thirteen are in the gallery as requested. Any can be removed in one line of `frontend/src/lib/gallery.js`. |
| 4 | **Address.** The site shows "Pahari Marga / 15th Street, Lakeside, Pokhara 33700, Nepal". | Shown as given. |
| 5 | **Ratings and history** (Google 4.7/292, Tripadvisor 4.9/176, "since 1986"). Could not be verified. | Not shown. |

## Things to know about this stage

- **The owner's menu editor does not change the public menu yet.** The website shows the printed menu; the
  editor changes the separate database menu. The dashboard says so. They will be joined in the backend stage.
- **Customer and staff sign-in are not switched on.** Their pages explain this and accept nothing.
- **Employee permissions are a design preview only.** Nothing is saved or enforced yet.
- **WhatsApp** opens a chat with the shop. It does not send or confirm a table request.
- **No notifications, no table-capacity tracking, no payments, no food ordering.**

## Decisions for the owner

- How should customers sign in later: email and password, phone and one-time code, or Google? Each needs its own setup.
- Which permissions should a new employee have by default?
- How long should guest contact details be kept?
