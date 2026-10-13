# Threat model — Wendy Juice Shop

**Baseline:** commit `834e59f26541e51977dcec21047423aa82f2c1a9` (the audited commit) on `release/wendy-production-review`, plus the remediation changes of 13 October 2026 described in `04-findings-and-recommendations.md` ("Status update"), committed after it on the same branch (`git log 834e59f..release/wendy-production-review`).

Labels: **[Verified]** = control read in code and/or covered by a test that was run. **[Open]** = unresolved
finding. **[Recommended]** = not implemented. **[Deployment]** = can only be checked on a real server, which
does not exist yet.

## 1. What the system is

A café website with table-booking **requests**. No payments, ordering or delivery. Staff approve each
request by hand; no table capacity is modelled.

```
Visitor / customer / staff browser
        │ HTTPS
        ▼
   Caddy (public: 80, 443)  ── serves the built site
        │ /api/*  (private network)
        ▼
   FastAPI (2 workers)  ──►  PostgreSQL (private, named volume)
        │
        └─► SMTP provider (only if configured; password-reset emails)

Operator ── SSH ──► server: CLI (create owner, import menu), backups ──► encrypted file ──► off-server storage
```

## 2. What is worth protecting

| Asset | Where | Why it matters |
|---|---|---|
| Customer and guest contact details (name, phone, email, notes) | `bookings`, `accounts` tables; backups | Personal data of real people |
| Password hashes | `accounts.password_hash`; backups | Offline guessing if stolen |
| Sessions | `account_sessions` (digests); browser cookie | Acting as a customer, employee or owner |
| Owner account | `accounts` (role `owner`) | Reads all contact details, manages staff, changes menu and rules |
| Reset and staff setup links | Email, or passed by the owner by hand | Set a password for an account |
| Booking records and their status | `bookings`, `booking_status_history` | The café's working diary; wrong status means a lost or phantom table |
| Menu and booking rules | `menu_*`, `booking_settings` | Public face and intake rules |
| Secrets: database password, SMTP password, backup private key, storage credentials | `.env.production` on the server; off-server | See `secrets.md` |
| Availability of the booking form | Whole stack | Lost requests |

## 3. Who might attack, and what they can do

| Actor | Starting position |
|---|---|
| Anonymous internet user or bot | Can call every public endpoint and load the site |
| Registered customer | Has a valid customer session |
| Employee (possibly disgruntled or with a stolen device) | Has a staff session with some permissions |
| Someone with a stolen or guessed password | Becomes that account |
| Someone who obtains a backup file or log file | Offline access to its contents |
| Someone who compromises the server | Everything on it |
| A compromised dependency or base image | Code execution in the API or in visitors' browsers |

## 4. Trust boundaries

1. **Browser ↔ Caddy.** Everything from the browser is untrusted, including which sign-in page was used.
2. **Caddy ↔ API.** The API trusts Caddy for the visitor's address (`X-Forwarded-For`) only when
   `TRUST_PROXY_HEADERS` is set (`backend/app/rate_limit.py:65`).
3. **API ↔ database.** The API is the only database client; it uses one database account.
4. **Server ↔ operator.** Shell access is full control: the CLI can create owners.
5. **Server ↔ backup storage.** The server can write backups but, holding only the public key, cannot read them.

## 5. Threats and their treatment

### Spoofing identity

| Threat | Treatment |
|---|---|
| Guessing passwords online | **[Verified]** Argon2id hashing (`security.py:26`); limits per email+address, per address, per email (`routers/auth.py:125-130`); `test_login_is_rate_limited` |
| Locking the owner out by failing on purpose | **[Verified]** Per email+address limit with a high per-email cap (`routers/auth.py:129-130`); `test_one_stranger_cannot_lock_an_account_for_everyone`. Residual: about ten addresses can still reach the per-email cap |
| Stolen staff or owner password | **[Recommended]** Second factor (F-05; plan in `mfa-plan.md`). Today: password, limits, and session revocation by the owner |
| Using the owner sign-in page to become an owner | **[Verified]** Role comes from the account (`routers/auth.py:136-138`); `test_the_sign_in_page_never_decides_the_role` |
| Registering as staff or owner | **[Verified]** `RegisterIn` forbids extra fields; role fixed to customer (`routers/auth.py:109`); `test_registration_rejects_privileged_fields` |
| Stealing a session cookie by script | **[Verified]** `HttpOnly` cookie (`routers/auth.py:68`). **[Open]** CSP is report-only (F-04), so it does not yet block injected script |
| Intercepting a reset or setup link | **[Verified]** Single-use, expiring, hashed, in the URL fragment so it is not in server logs (`routers/auth.py:77-93`). Residual: the link is as safe as the channel it is sent over |

### Tampering

| Threat | Treatment |
|---|---|
| Customer sets their own booking to confirmed | **[Verified]** Status, reference, customer link and notes are server-set (`booking_service.py:142-175`); `test_customer_booking_is_pending_linked_and_uses_server_values` |
| Cross-site request changes data using a signed-in user's cookie | **[Verified]** `SameSite=Strict`, CSRF token (`security.py:75-84`), origin check (`main.py`, `reject_cross_site_writes`); `test_csrf_token_and_origin_are_required_for_changes` |
| Employee acts beyond their permissions | **[Verified]** Checked per request and per action (`security.py:114-121`, `booking_service.py:263`); `test_each_action_needs_its_own_permission` |
| Two staff overwrite each other | **[Verified]** Row lock and version check (`booking_service.py:208-227`); `test_simultaneous_staff_actions_cannot_both_win` |
| SQL injection | **[Verified]** ORM and bound parameters only (reviewed; no string-built SQL in `backend/app/`) |
| Script injected through booking text, menu text or names | **[Verified]** React escapes output; no raw-HTML rendering in `frontend/src`. **[Open]** no enforcing CSP as a second layer (F-04) |
| Tampered dependency | **[Verified]** Backend installs only hash-pinned packages (`backend/Dockerfile:12`); frontend uses `npm ci` with its lockfile. **[Open]** base images are referenced by tag (F-18) |

### Repudiation

| Threat | Treatment |
|---|---|
| Staff deny changing a booking | **[Verified]** Status history and activity log with actor and time (`booking_service.py:280-284`, `activity.py`); `test_activity_log_records_staff_and_owner_actions` |
| Unnoticed sign-ins to staff accounts | **[Open]** Sign-ins are not recorded (F-12) |

### Information disclosure

| Threat | Treatment |
|---|---|
| Customer reads another customer's booking | **[Verified]** Every query filtered by the session's customer id (`routers/customer.py:43`, `:63`); `test_customer_sees_only_their_own_bookings` |
| Anyone looks up a booking by reference | **[Verified]** No such endpoint; `test_no_public_endpoint_lists_or_reads_bookings` |
| Employee without contact permission reads phone or email | **[Verified]** Fields are omitted from the response (`booking_service.py:398`, `:418-419`); `test_contact_details_are_left_out_of_every_response_without_permission`. **[Open]** free-text fields may still contain them (F-10) |
| Customer data in application logs | **[Verified, fixed 13 Oct 2026]** Unexpected errors are logged without exception text or statement values (`safe_logging.py`, `main.py:32-68`, `database.py:24`); `tests/test_logging.py`. Confirmed with a real server process on a disposable database |
| Customer data in the database's own log | **[Verified in code; Deployment]** `docker-compose.prod.yml:39`. Confirmed on a disposable container; must be re-set if the database moves |
| Stolen backup file | **[Verified]** Encrypted to a public key; the server cannot decrypt (`scripts/backup.sh:53`). **[Deployment]** off-server copy and schedule not set up (F-03 partly open) |
| Whether an email is registered | **[Verified]** Sign-in and reset do not reveal it. **[Open]** registration does (F-13) |
| Error pages leaking internals | **[Verified]** Generic message and a reference id only (`main.py:32-47`); API docs off in production (`main.py:22`) |
| Visitors' addresses sent to a third party | **[Open, accepted]** Google Fonts is loaded from Google (`frontend/index.html:9-11`) |

### Denial of service

| Threat | Treatment |
|---|---|
| Flooding the booking form | **[Verified]** Limits per address (`routers/public.py:89-90`), request size cap (`frontend/Caddyfile`). **[Open]** no bot challenge (F-09) |
| Exhausting the database through the rate limiter | **[Recommended]** Each limited request uses an extra short database connection (`rate_limit.py:23`); pool is 5+5 per worker (`database.py`). Add a proxy-level limit if abused |
| Loss of the server | **[Deployment]** Encrypted backup and restore rehearsal exist and were tested with synthetic data; scheduling and off-server copies are **not verified** |

### Elevation of privilege

| Threat | Treatment |
|---|---|
| Employee grants themselves permissions | **[Verified]** Owner-only router (`routers/owner.py:22`); profile update has no permission field; `test_employees_cannot_manage_employees_or_their_own_privileges` |
| Employee confirms the provisional booking rules | **[Verified]** Owner-only (`routers/staff.py:187-188`) |
| Removed employee keeps access | **[Verified]** Account checked on every request (`security.py:70`); `test_deactivation_takes_effect_immediately` |
| Container escape after API compromise | **[Verified]** API runs as a non-root user (`backend/Dockerfile`). **[Deployment]** host hardening not assessed |

## 6. Accepted risks (owner should confirm)

- Single server: an outage or compromise affects everything.
- No second factor for staff at launch (F-05), if the owner accepts the plan's timing.
- Registration reveals registered emails (F-13).
- Fonts loaded from Google.
- Staff who can view a booking can read its free-text fields (F-10).

## 7. Out of scope

Physical security of staff phones and the café's network, the email provider's security, the hosting
provider's security, and social engineering of the owner. These are real risks that this repository cannot address.
