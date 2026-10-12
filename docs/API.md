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
  `not_allowed_now` (409), `idempotency_conflict` (409), `booking_unavailable` (409). Stack traces are never returned.
- **Time.** Booking dates and times are in `Asia/Kathmandu`. Timestamps are ISO 8601 with timezone.

## Public

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness check |
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
| `POST /login` | anyone | Body: `email`, `password`, `portal?` (`customer`/`employee`/`owner`). `portal` can only refuse a sign-in on the wrong page; it never changes the role |
| `GET /me` | signed in | Account, role, permissions, `csrf_token` |
| `POST /logout` | signed in | Ends this session |
| `PATCH /profile` | signed in | `full_name`, `phone` only |
| `POST /password` | signed in | `current_password`, `new_password`; signs out other devices |
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

## Owner (`/api/owner`, role `owner`)

| Endpoint | Purpose |
|---|---|
| `GET /permissions` | The permission keys and labels |
| `GET /employees` | Employees with permissions, active sign-ins, whether a password is set |
| `POST /employees` body `email`, `full_name`, `permissions?` | Creates an employee with no password and (by default) no permissions. Returns a one-time `setup_url` |
| `POST /employees/{id}/setup-link` | New one-time link; earlier links stop working; signs the employee out |
| `PATCH /employees/{id}` body `full_name?`, `permissions?`, `is_active?` | Takes effect on the employee's next request |
| `POST /employees/{id}/revoke-sessions` | Sign the employee out everywhere |
| `GET /activity?limit&offset&actor_id` | Activity log, newest first |
