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

## Things to know

- **One menu.** The website and the dashboard's Menu tab now use the same menu in the database. The printed
  menu was imported once; the eight wording questions above are still shown exactly as printed, and the four
  the brief named are marked "Please check" in the Menu tab.
- **Customer accounts** use email and password. Guests can still request a table without an account.
- **Staff accounts** are created by the owner, who passes each employee a one-time link to choose a password.
- **No automatic messages.** No email, SMS or WhatsApp is sent to guests or staff. WhatsApp buttons open a chat
  with a message ready for a person to send.
- **Password reset by email is off** until an email provider is configured. Until then the site says so, and
  the owner can issue staff a new link from the Team tab.
- **No table-capacity tracking, payments or food ordering.**

## Decisions for the owner

- **How many tables and seats are there, and how long does a booking last?** Unknown, so the system does not
  track availability; staff check by hand.
- **Which email service should send password-reset emails?** Needed before customers can reset passwords themselves.
- **Should Google sign-in or phone one-time codes be added later?** Not built; each needs its own provider.
- **Which permissions should a typical employee have?** New employees start with none. This includes the three
  inventory permissions: no existing employee was given inventory access when it was added.
- **Should inventory be used, and who records stock?** The Inventory tab starts empty. Nothing was filled in
  from guesses or copied from the menu; real stock levels have to be entered by the shop.
- **How long should guest and customer details, and the activity log, be kept?** Nothing is deleted automatically.
- **Should customers who booked as guests be able to link those bookings to an account?** Not done: matching
  on phone or email alone is not safe. It would need a verified email or phone.
