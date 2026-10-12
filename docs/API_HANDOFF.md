# API handoff: frontend stage → backend stage

Last updated: 12 October 2026. The backend was **not changed** in the frontend stage. This document lists what
the frontend uses today and what the backend stage needs to add.

## 1. Existing endpoints the frontend uses (implemented, unchanged)

| Endpoint | Used by |
|---|---|
| `GET /api/booking/config` | Booking form: windows, group sizes, notice, whether requests are open |
| `POST /api/bookings` | Booking form: stores a `pending` request; returns `reference`, `status`, `message` |
| `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` | Owner sign-in at `/owner/login` and the dashboard at `/owner` |
| `GET /api/owner/bookings`, `GET`/`PATCH /api/owner/bookings/{id}`, `POST /api/owner/bookings/{id}/status` | Owner → Table requests |
| `GET`/`PUT /api/owner/settings` | Owner → Booking settings |
| `GET /api/owner/menu`, `POST`/`PATCH`/`DELETE /api/owner/menu/items…` and `…/categories…` | Owner → Menu editor |
| `GET /api/menu` | **Not called by the public site in this stage** (see section 2). Still served and still used when `VITE_MENU_SOURCE=api`. |

## 2. Menu: two sources until the import is done

| | Public website | Owner menu editor |
|---|---|---|
| Source now | `frontend/src/data/menuFromPdf.js` (the printed menu, 13 categories, 79 items) | Database tables `menu_categories`, `menu_items` (25 older items from public listings) |
| Loaded through | `frontend/src/lib/menuService.js` | `GET /api/owner/menu` |

The dashboard tells the owner that edits do not reach the website yet. There is no automatic fallback between
the two sources: if the selected one fails, the site shows an error and a link to the PDF.

**Backend work to restore one shared menu:**

1. Add a new Alembic migration (do not edit `0001`/`0002`) that:
   - adds `menu_items.addons` (JSON list of `{label, price, unit?}`) and `menu_categories.notes` (JSON list of
     `{label, price, prefix?}`), plus optional `source_document` / `source_page`;
   - allows `source = 'owner_pdf'` in the `ck_menu_items_source` check;
   - optionally adds a stable `slug` per item so the frontend IDs (`brunch-vegan-porridge`) survive.
2. Import the 79 items from `menuFromPdf.js`. Decide with the owner what happens to the 25 existing rows and any
   edits made to them (replace, archive, or keep hidden); do not delete owner edits silently.
3. Return `addons` and `notes` from `GET /api/menu` and accept them in the owner endpoints.
4. Add add-on and note fields to the owner menu editor.
5. Set `VITE_MENU_SOURCE=api`, then remove the notice in `frontend/src/owner/MenuPanel.jsx`.

## 3. Proposed customer API — NOT IMPLEMENTED

None of these endpoints exist. `/customer/login` is a disabled form; `/customer` is a development-only preview
with fictional data.

| Proposed endpoint | Purpose |
|---|---|
| `POST /api/customer/register` | Create an account (name, email or phone, password or one-time code) |
| `POST /api/customer/login`, `POST /api/customer/logout`, `GET /api/customer/me` | Session, separate from the owner session |
| `GET /api/customer/bookings` | The signed-in customer's own bookings, upcoming and past |
| `GET /api/customer/bookings/{reference}` | One of their own bookings |
| `POST /api/customer/bookings` | Create a booking linked to the account (guest `POST /api/bookings` stays) |
| `POST /api/customer/bookings/{reference}/cancellation-request` | Ask the shop to cancel; staff decide |

Requirements:

- **Ownership on every request.** A customer may only read or act on bookings whose `customer_id` is theirs.
  Return 404, not 403, for other people's references.
- Add `bookings.customer_id` (nullable, for guest requests) and a `cancellation_requested_at` field or status.
- Same protections as the owner session: hashed passwords, HttpOnly SameSite cookie, CSRF token, rate-limited
  login, no account enumeration.
- Decide how earlier guest requests are linked to a new account (verified phone or email only).
- Google sign-in or SMS one-time codes need configured providers; the UI shows no such buttons until they exist.

## 4. Proposed employee API — NOT IMPLEMENTED

None of these endpoints exist. `/employee/login` is a disabled form; `/employee` and the owner's "Team
(preview)" tab are development-only previews with fictional data.

| Proposed endpoint | Purpose | Permission required |
|---|---|---|
| `POST /api/employee/login`, `POST /api/employee/logout`, `GET /api/employee/me` | Session; `me` returns the granted permissions | — |
| `GET /api/employee/bookings` (`status`, `date_from`, `date_to`) | List | `view_bookings` |
| `GET /api/employee/bookings/{id}` | Details; phone and email omitted without `view_contact` | `view_bookings` |
| `POST /api/employee/bookings/{id}/status` → `confirmed` / `declined` | Approve or decline | `approve_decline` |
| `POST /api/employee/bookings/{id}/status` → `cancelled` | Cancel | `cancel` |
| `POST /api/employee/bookings/{id}/check-in` | Mark arrived (new `checked_in` status) | `check_in` |
| Menu and settings endpoints | As the owner's | `edit_menu`, `edit_settings` |
| `GET`/`POST /api/owner/employees`, `PATCH`/`DELETE /api/owner/employees/{id}` | Owner manages staff accounts | owner only |
| `PUT /api/owner/employees/{id}/permissions` | Owner sets permissions | owner only |

Permission keys used by the frontend (`frontend/src/preview/permissions.js`): `view_bookings`, `view_contact`,
`approve_decline`, `cancel`, `check_in`, `edit_menu`, `edit_settings`.

Requirements:

- **The server enforces every permission on every request.** Hiding a button in the browser is not security.
  Contact details must be left out of the response itself when `view_contact` is missing.
- Permissions are read from the database per request, so a change or deactivation by the owner takes effect at
  once and ends the employee's sessions.
- Only the owner can create employees or change permissions; an employee can never change their own.
- **Activity log:** record who (owner or which employee) did what to which booking and when (status changes,
  check-ins, cancellations, menu and settings edits, permission changes), and show it to the owner.
- Add `checked_in` to the booking status check constraint and to the allowed transitions (`confirmed → checked_in`).
- Tests for each permission: allowed, denied, deactivated employee, and contact-detail redaction.

## 5. Frontend pieces ready to connect

| Screen | File | What to do in the backend stage |
|---|---|---|
| Customer / staff sign-in | `frontend/src/auth/ComingSoonLogin.jsx` | Replace with real forms calling the new login endpoints |
| Customer bookings | `frontend/src/preview/CustomerPreview.jsx` | Replace fixtures with `GET /api/customer/bookings`; wire the cancellation request |
| Staff bookings | `frontend/src/preview/EmployeePreview.jsx` | Replace fixtures and the permission picker with `GET /api/employee/me` |
| Team and permissions | `frontend/src/preview/TeamPanel.jsx` | Wire to the owner employee endpoints and show the tab in all builds |

The preview switch (`frontend/src/lib/preview.js`) requires both the Vite dev server and
`VITE_ENABLE_PREVIEW=true`. Production builds contain none of the preview screens or fixtures.
