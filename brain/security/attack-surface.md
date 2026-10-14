# Attack surface

**Baseline:** commit `834e59f26541e51977dcec21047423aa82f2c1a9` (the audited commit) on `release/wendy-production-review`, plus the remediation changes of 13 October 2026 described in `04-findings-and-recommendations.md` ("Status update"), committed after it on the same branch (`git log 834e59f..release/wendy-production-review`). Entries marked "added 14 Oct 2026" describe the staff inventory feature, committed after that on the same branch.

Everything an outsider or a signed-in user can reach, taken from the code. Route lists come from the router
files; line numbers point at the route decorator.

## 1. Network exposure (production stack, `docker-compose.prod.yml`)

| Listener | Reachable from | Notes |
|---|---|---|
| Caddy :80 | Internet | Redirects to HTTPS |
| Caddy :443 | Internet | The only real entry point: static site and `/api/*` |
| API :8000 | Compose network only | No `ports:` entry. Runs as a non-root user |
| PostgreSQL :5432 | Compose network only | No `ports:` entry |
| Caddy admin :2019 | Inside its container only | Not published |
| SSH | Operator | Host-level; **not assessed** (no server exists) |

**Deployment check pending:** confirm on the real host, from outside, that only 80 and 443 answer.

Development stack (`docker-compose.yml`): API and dev server are bound to `127.0.0.1`; the database is not
published. Running `npm run dev` directly listens on all interfaces (F-16).

## 2. HTTP endpoints

### Public, no session (`backend/app/routers/public.py`, `auth.py`)

| Endpoint | Line | Input | Limits and controls |
|---|---|---|---|
| `GET /api/health` | public.py:23 | none | No database access |
| `GET /api/ready` | public.py:29 | none | Returns only ready / unavailable / migration_pending |
| `GET /api/menu` | public.py:44 | none | Published items only; cacheable 60 s |
| `GET /api/booking/config` | public.py:59 | none | Rules only, no guest data |
| `POST /api/bookings` | public.py:84 | Name, phone, email, date, time, party size, notes, idempotency key | 5 / 10 min and 30 / day per address; strict schema; always `pending`. No bot challenge (F-09) |
| `GET /api/auth/config` | auth.py:96 | none | Reveals whether email reset is enabled |
| `POST /api/auth/register` | auth.py:101 | Name, email, password, phone | 5 / hour per address; always a customer; reveals a registered email (F-13) |
| `POST /api/auth/login` | auth.py:121 | Email, password, optional portal | 5 / 15 min per email+address, 20 per address, 50 per email; uniform failure answer. Password only (F-05) |
| `POST /api/auth/password-reset/request` | auth.py:182 | Email | 5 / hour per address, 3 / hour per email; uniform answer; email sent after the response |
| `POST /api/auth/password-reset/confirm` | auth.py:210 | Token, new password | 10 / 15 min per address; single-use hashed token |

### Any signed-in account (`auth.py`)

| Endpoint | Line | Controls |
|---|---|---|
| `GET /api/auth/me` | 142 | Session |
| `POST /api/auth/logout` | 148 | Session + CSRF |
| `PATCH /api/auth/profile` | 155 | Session + CSRF; name and phone only |
| `POST /api/auth/password` | 168 | Session + CSRF; current password; 5 / 15 min |

### Customer role (`customer.py`)

| Endpoint | Line | Controls |
|---|---|---|
| `POST /api/customer/bookings` | 21 | Linked to the session's customer; 10 / 10 min |
| `GET /api/customer/bookings` | 33 | Filtered by customer id; page size ≤ 50 |
| `GET /api/customer/bookings/{reference}` | 59 | Own bookings only; otherwise 404 |
| `POST /api/customer/bookings/{reference}/cancellation-request` | 69 | Own bookings only; does not change status; 10 / hour |

### Staff: owner or employee (`staff.py`, router guard at line 42)

| Endpoint | Line | Extra requirement |
|---|---|---|
| `GET /bookings`, `GET /alerts`, `GET /bookings/{id}` | 57, 92, 107 | `bookings.view_all`, or `view_assigned` for own assignments |
| `POST /bookings/{id}/status` | 116 | The permission for the target status; version; time rules |
| `PATCH /bookings/{id}` | 123 | `bookings.edit_notes`; version |
| `POST /bookings/{id}/cancellation` | 142 | `bookings.cancel`; version |
| `POST /bookings/{id}/assign`, `GET /assignable` | 130, 150 | Owner only |
| `GET`, `PUT /settings` | 178, 183 | `booking_settings.manage`; only the owner may confirm the rules |
| `GET /menu`; `POST`, `PATCH`, `DELETE` on `/menu/categories…`, `/menu/items…` | 266–346 | `menu.manage` |

### Inventory: owner, or employee with `inventory.view` (`inventory.py`, router guard at line 33) — added 14 Oct 2026

| Endpoint | Line | Extra requirement |
|---|---|---|
| `GET /api/staff/inventory/items`, `GET /items/{id}`, `GET /movements` | 61, 105, 138 | None beyond `inventory.view` |
| `POST /items`, `PATCH /items/{id}` | 112, 121 | `inventory.manage_items`; version on edit; unique name |
| `POST /items/{id}/movements` | 128 | `inventory.adjust_stock`; idempotency key; version for corrections; row lock |

Writes are rate-limited to 300 per account per 15 minutes (`inventory.py:42`). Inputs: item names, reasons
(free text, max 300 characters, control characters refused) and decimal quantities. No route edits or deletes a
movement, and a database trigger refuses `UPDATE`/`DELETE` on `inventory_movements` (migration `0004`).
Inventory holds no customer data and no costs; free-text reasons are visible to everyone with `inventory.view`.

### Owner only (`owner.py`, router guard at line 22)

`GET /permissions` (47), `GET /employees` (52), `POST /employees` (59), `POST /employees/{id}/setup-link`
(81), `PATCH /employees/{id}` (95), `POST /employees/{id}/revoke-sessions` (117), `GET /activity` (126).

Total: 10 public, 4 signed-in, 4 customer, 17 staff, 6 inventory, 7 owner. API documentation routes are disabled in
production (`backend/app/main.py:22`, `:24`).

## 3. Cross-cutting request handling

| Layer | Where | What it does |
|---|---|---|
| Body size cap | `frontend/Caddyfile` (`request_body`) | 256 KB |
| Origin check | `backend/app/main.py`, `reject_cross_site_writes` (line 51) | Refuses state-changing requests from other origins |
| Unexpected-error handling | same function, `_server_error` (line 32) | Generic answer with a reference id; safe log line |
| Session + CSRF | `backend/app/security.py:75-84` | Cookie lookup by digest, expiry, active flag, CSRF header |
| Role and permission | `security.py:95-121`, `models.py:52-57` | From the database row, per request |
| Validation | `backend/app/schemas.py` | Unknown fields rejected; lengths capped |
| Rate limits | `backend/app/rate_limit.py` | PostgreSQL-backed, keys stored as digests |

## 4. Browser-side surface

| Item | Detail |
|---|---|
| Scripts | One module bundle and lazy chunks from `/assets/`. No inline script, no `eval`, no workers (checked in the built bundle) |
| Styles | One stylesheet from `/assets/`; Google Fonts stylesheet; two components use `style=""` attributes |
| Images | Own files under `/images/`; one inline (data:) favicon |
| Fonts | `fonts.gstatic.com` |
| Network calls | Only `/api/...` on the same origin (`frontend/src/lib/api.js`) |
| Embeds, frames, third-party scripts, analytics | None |
| Outbound links | Google Maps, WhatsApp, Facebook, Tripadvisor, HappyCow; all with `rel="noopener noreferrer"` |
| Browser storage | One non-sensitive preference (`frontend/src/staff/StaffApp.jsx`, alert sound) |
| Token in URL | Reset/setup token in the fragment only; removed from the address bar on load (`frontend/src/auth/AccountPages.jsx`, `ResetPage`) |
| Content Security Policy | **Report-only** (`frontend/Caddyfile:22`): validated with no violations across the main flows, but **not enforced by browsers** (F-04 open) |
| Other headers | HSTS, `nosniff`, frame denial, referrer and permissions policies (`frontend/Caddyfile`) |

## 5. Non-HTTP surface

| Surface | Who can reach it | Risk |
|---|---|---|
| Admin CLI `python -m app.cli` (`backend/app/cli.py`) | Anyone with a shell on the server | Creates owners, sets any password, imports the menu. Server access is full control. Unexpected errors print type, error code and location, not the error text (`cli.py:46-75`) |
| Database | API only | One database account with full rights on its database |
| Backups | Whoever can read the backup folder or storage | Encrypted to a public key; useless without the private key |
| Outbound email | API to the SMTP provider | Only password-reset messages; disabled unless configured |
| Staff setup links | Owner passes them by hand (WhatsApp, in person) | Single-use, 72 hours; whoever holds the link sets the password |
| Logs | Whoever can read container logs | No customer data in application or database logs by design (tested); proxy log holds IP addresses |
| Build and supply chain | Developer machine, PyPI, npm, Docker Hub | Backend hash-pinned; frontend lockfile; base images by tag (F-18) |
| Git repository | Whoever has access to it on GitHub | No secrets found in history. It does contain photos of identifiable guests |
| Connected Vercel project | The Vercel account | Serves an older frontend-only build of `main`; not part of this stack. **Not assessed** |

## 6. Data that leaves the system

| To | What |
|---|---|
| Google (fonts) | Visitor IP address and user agent, on every page load |
| SMTP provider (if configured) | Recipient email, name and a reset link |
| WhatsApp, Maps, Facebook and review sites | Only when a person clicks a link; a prepared message may contain a guest's name and booking reference, sent by the staff member themselves |
| Off-server backup storage (if configured) | Encrypted database dumps |

## 7. Not assessed

The server's operating system, firewall and SSH configuration; the hosting provider; DNS; the SMTP
provider; the GitHub and Vercel account settings; staff devices. None can be evaluated from this repository.
