# API reference

All endpoints are under `/api` and exchange JSON. In development, interactive docs are at
`http://localhost:8000/api/docs` (switched off in production).

## Conventions

- **Sessions.** Signing in sets an `HttpOnly`, `SameSite=Strict` cookie (`Secure` in production). Nothing is
  stored in browser storage and there are no JWTs.
- **CSRF.** Every `POST`/`PUT`/`PATCH`/`DELETE` made with a session must send the session's `csrf_token`
  (returned by login, register and `GET /api/auth/me`) in an `X-CSRF-Token` header. Requests whose `Origin`
  is not the site itself or in `CORS_ORIGINS` are refused.
- **Roles.** `customer`, `employee`, `owner`. The role and permissions come from the account in the
  database on every request. No endpoint accepts a role, and unknown fields in any request body are rejected.
- **Errors.** `{"error": {"code": "...", "message": "...", "fields": {"field": "message"}}}`. Common codes:
  `validation_error` (422), `not_authenticated` (401), `forbidden` (403), `csrf_failed` (403), `not_found`
  (404), `rate_limited` (429, with `Retry-After`), `stale_update` (409), `invalid_transition` (409),
  `not_allowed_now` (409), `idempotency_conflict` (409), `booking_unavailable` (409), and for inventory
  `insufficient_stock`, `unit_locked`, `item_archived`, `name_taken` (all 409). Stack traces are never returned.
- **Time.** Booking dates and times are in `Asia/Kathmandu`. Timestamps are ISO 8601 with timezone.

## Public

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness: the API process is up |
| `GET /api/ready` | Readiness: database reachable and migrated. `503` otherwise, with no connection details |
| `GET /api/menu` | The menu (published items only), with `addons` per item and `notes` per section |
| `GET /api/booking/config` | Whether requests are open, group sizes, notice, weekday windows, closed/special dates |
| `POST /api/bookings` | Guest table request. Returns only `reference`, `status: "pending"`, `message`. `201` new, `200` replay |

Booking body: `full_name`, `phone` (with country code), `email?`, `requested_date`, `requested_time`,
`party_size`, `special_requests?`, `idempotency_key?`. Reusing an idempotency key with different details
returns `409 idempotency_conflict`. There is no endpoint to look a booking up by reference.

## Accounts (`/api/auth`)

| Endpoint | Who | Purpose |
|---|---|---|
| `GET /config` | anyone | `password_reset_by_email`, `min_password_length` |
| `POST /register` | anyone | Create a **customer** account and sign in. Body: `full_name`, `email`, `password` (12+), `phone?` |
| `POST /login` | anyone | Rate-limited per email and address. Body: `email`, `password`, `portal?` (`customer`/`employee`/`owner`). `portal` can only refuse a sign-in on the wrong page; it never changes the role |
| `GET /me` | signed in | Account, role, permissions, `csrf_token` |
| `POST /logout` | signed in | Ends this session |
| `PATCH /profile` | signed in | `full_name`, `phone` only |
| `POST /password` | signed in | `current_password`, `new_password`, `confirm_new_password`. `204` on success. `422` with per-field messages when a field is empty, the new password is under 12 characters, the confirmation differs, the current password is wrong, or the new one equals it; nothing changes then. 5 complete attempts per 15 minutes (`429`). On success other devices are signed out and unused reset/setup links stop working |
| `POST /password-reset/request` | anyone | Always `202` with the same answer. Says so when email delivery is not configured |
| `POST /password-reset/confirm` | anyone | `token`, `new_password`. Tokens are single-use, short-lived, stored as hashes; all sessions are signed out |

Owners are created only with the server command (`python -m app.cli create-owner`). Employees are created
only by the owner. There is no public owner or employee registration.

## Customer (`/api/customer`, role `customer`)

| Endpoint | Purpose |
|---|---|
| `POST /bookings` | Same body as the guest request; linked to the signed-in customer by the server |
| `GET /bookings?when=upcoming\|past&limit&offset` | Own bookings, paginated |
| `GET /bookings/{reference}` | One own booking (`404` for anyone else's) |
| `POST /bookings/{reference}/cancellation-request` | Body `reason?`. Asks staff to cancel; the status does not change until staff decide |

Customer responses never include internal notes, the assigned employee, history or the version.
`cancellation` shows `status` (`pending`/`approved`/`declined`), `reason` and staff's `response`.

## Staff (`/api/staff`, role `owner` or `employee`)

| Endpoint | Permission (owner always passes) |
|---|---|
| `GET /bookings?status&date_from&date_to&cancellation=pending&limit&offset` | `bookings.view_all`, or `bookings.view_assigned` (then only bookings assigned to them) |
| `GET /bookings/{id}` (includes status history) | as above; out of scope is `404` |
| `GET /alerts` → `pending_count`, `newest_pending_id`, `cancellation_requests` | as above |
| `POST /bookings/{id}/status` body `status`, `version`, `reason?` | `bookings.approve` → confirmed, `bookings.decline` → declined, `bookings.cancel` → cancelled, `bookings.check_in` → checked_in, `bookings.complete` → completed, `bookings.mark_no_show` → no_show |
| `PATCH /bookings/{id}` body `internal_notes`, `version` | `bookings.edit_notes` |
| `POST /bookings/{id}/cancellation` body `decision` (`approve`/`decline`), `version`, `response?` | `bookings.cancel` |
| `POST /bookings/{id}/assign` body `employee_id` or `null`, `version` | owner only |
| `GET /assignable` | owner only |
| `GET`/`PUT /settings` | `booking_settings.manage` (only the owner may change `owner_confirmed`) |
| `GET /menu`, `POST`/`PATCH`/`DELETE /menu/items…`, `/menu/categories…` | `menu.manage` |

- `phone` and `email` are `null` and `contact_visible` is `false` in every staff response unless the
  viewer has `bookings.view_contact`.
- `version` is the booking's version the client last saw. If the booking changed since, the server answers
  `409 stale_update` and changes nothing. Rows are locked while a change is applied.
- Each booking lists `allowed_statuses` for the current viewer at the current time.

### Status rules

| From | To |
|---|---|
| `pending` | `confirmed`, `declined`, `cancelled` |
| `confirmed` | `checked_in`, `cancelled`, `no_show` |
| `checked_in` | `completed` |
| `declined`, `cancelled`, `completed`, `no_show` | final |

Time rules: a request whose time has passed cannot be confirmed; check-in only on the booking's date;
no-show only after its time. Every change is recorded with who, when and the reason.

## Inventory (`/api/staff/inventory`, owner or employee with `inventory.view`)

Staff only. Visitors get `401`, customers and employees without `inventory.view` get `403`, before any
inventory data is read. Nothing here is used by `/api/menu` or any public route.

| Endpoint | Permission (owner always passes) |
|---|---|
| `GET /items?search&category&status=active\|archived\|all&low_stock&limit&offset` → `items`, `total`, `low_stock_count` | `inventory.view` |
| `GET /items/{id}` | `inventory.view` |
| `POST /items` body `name`, `category`, `unit`, `low_stock_threshold?`, `opening_quantity?`, `idempotency_key` | `inventory.view` + `inventory.manage_items` |
| `PATCH /items/{id}` body `version`, `name?`, `category?`, `unit?`, `low_stock_threshold?`, `is_active?` | `inventory.view` + `inventory.manage_items` |
| `POST /items/{id}/movements` body `kind` (`stock_in`/`stock_out`/`adjustment`), `quantity`, `reason?`, `version?`, `idempotency_key` | `inventory.view` + `inventory.adjust_stock` |
| `GET /movements?item_id&limit&offset` (newest first) | `inventory.view` |

- **Categories:** `fruit_veg`, `dairy`, `coffee_tea`, `dry_goods`, `packaging`, `cleaning`, `other`.
  **Units:** `kg`, `litre`, `piece`.
- **Quantities** are sent and returned as decimal strings (numbers are accepted on input): at most 3 decimal
  places, never negative, whole numbers for `piece`. Responses drop trailing zeros (`"2.5"`, `"100"`).
- **Movements.** `stock_in`/`stock_out`: `quantity` is the amount (more than 0). `adjustment`: `quantity` is the
  counted stock, which becomes the new balance; `reason` and the item's current `version` are required. A stock
  out larger than the stock is `409 insufficient_stock`. Each movement returns `quantity_change`,
  `balance_after`, `actor_name`, `actor_role`, `reason` and `created_at`. There is no route to edit or delete one.
- **Opening stock.** `opening_quantity` above 0 on `POST /items` is recorded as an `opening` movement.
- **Idempotency.** The same `idempotency_key` with the same body returns the entry already recorded (`200`
  instead of `201`); with a different body it is `409 idempotency_conflict`. Item creation without opening
  stock relies on the unique name instead (`409 name_taken`, case-insensitive).
- **Versions.** `PATCH /items/{id}` and adjustments need the `version` last seen; otherwise `409 stale_update`.
  `PATCH` has no quantity field. `unit` cannot change once any movement exists (`409 unit_locked`).
  `is_active: false` archives an item; archived items take no movements (`409 item_archived`).
- **Rate limit.** 300 inventory changes per account per 15 minutes (`429`).

## Owner (`/api/owner`, role `owner`)

| Endpoint | Purpose |
|---|---|
| `GET /permissions` | The permission keys, labels and `requires` (the permission each one depends on, or `null`) |
| `GET /employees` | Employees with permissions, active sign-ins, whether a password is set |
| `POST /employees` body `email`, `full_name`, `permissions?` | Creates an employee with no password and (by default) no permissions. Returns a one-time `setup_url` |
| `POST /employees/{id}/setup-link` | New one-time link; earlier links stop working; signs the employee out |
| `PATCH /employees/{id}` body `full_name?`, `permissions?`, `is_active?` | Takes effect on the employee's next request. A permission without the one it `requires` is `422` (also on `POST /employees`) |
| `POST /employees/{id}/revoke-sessions` | Sign the employee out everywhere |
| `GET /activity?limit&offset&actor_id` | Activity log, newest first |
