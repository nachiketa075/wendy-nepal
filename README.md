# Wendy Juice Shop — website and table reservations

A café website for Wendy Juice Shop (Lakeside, Pokhara) with table reservations. Customers can request
tables and follow their bookings; the owner and employees manage requests from a dashboard.

It is a **table-reservation** site only. There is no food ordering, cart, delivery, payment or deposit.

- **Frontend:** React, Vite, Tailwind CSS (`frontend/`)
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic (`backend/`)
- **Database:** PostgreSQL
- **Local development:** Docker Compose

> **Not production-ready yet.** It runs and is tested locally, but real use still needs the owner's
> booking rules, an email provider for password resets, HTTPS hosting and the other items under
> [Before going live](#before-going-live). See also [docs/OWNER_CONFIRMATION.md](docs/OWNER_CONFIRMATION.md).

## What it does

| Area | Address | What works |
|---|---|---|
| Public site | `/`, `/menu` | Photos, menu from the database, business details, table request form (no account needed) |
| Customer | `/customer/login`, `/customer/register`, `/customer` | Register, sign in, request a table, see upcoming and past bookings with live status, ask to cancel, edit profile, change password |
| Owner | `/owner/login`, `/owner` | All bookings, confirm/decline/cancel/check-in/complete/no-show, notes, assign to employees, answer cancellation requests, booking settings, menu, team and permissions, activity log |
| Employee | `/employee/login`, `/employee` | Only what the owner has allowed: the same dashboard with tabs, bookings, contact details and buttons limited by permission |
| Password help | `/account/forgot`, `/account/reset` | Reset by emailed link (when email is configured); first password for invited employees |

The three sign-in pages share one sign-in service. The page used never decides the role: the server reads
it from the account and checks role and permissions on every request.

## Run it locally

You need Docker with the Compose plugin.

```bash
cp .env.example .env
# Put a database password in .env, for example:
#   POSTGRES_PASSWORD=$(openssl rand -hex 24)
docker compose up --build
```

- Website: <http://localhost:5173> (set `FRONTEND_PORT` in `.env` if that port is taken, and set
  `PUBLIC_SITE_URL` to match)
- API docs (development only): <http://localhost:8000/api/docs>

This Compose file is for development (auto-reload, test tools, migrations on start). Production uses
`docker-compose.prod.yml`; see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

The backend applies database migrations each time it starts. It does **not** load menu content on startup.

### 1. Create the owner account

Owner accounts can only be created on the server, with this command. There is no default login and no
owner sign-up page. You are prompted for a password of at least 12 characters (stored as an Argon2 hash).

```bash
docker compose exec backend python -m app.cli create-owner owner@example.com --name "Owner Name"
```

To set a new password for any account later (signs it out everywhere):

```bash
docker compose exec backend python -m app.cli set-password someone@example.com
```

### 2. Import the printed menu

The public menu and the owner's menu editor use the same database menu. Load the printed menu
(`backend/data/menu_cm_pdf.json`, transcribed from `CM.pdf`) into it once:

```bash
docker compose exec backend python -m app.cli import-menu                        # dry run: shows what would change
docker compose exec backend python -m app.cli import-menu --apply --hide-legacy  # write it
```

- Without `--apply` nothing is written; you get a summary.
- It is safe to run again: items are matched by a stable identifier, so nothing is duplicated.
- **Owner edits are kept.** Each imported item remembers what the import wrote. If the owner has changed an
  item since, a later import leaves it alone and lists it under "kept (edited by owner)".
- `--hide-legacy` hides the 25 older items that came from public listings. They stay in the editor (marked
  hidden) and can be shown again or deleted there. Without the flag they remain on the public menu.
- To take an imported item off the menu, untick "Show on website" rather than deleting it; a deleted imported
  item would be offered again by the next import.
- The original PDF stays downloadable at `/menu/wendy-juice-shop-menu.pdf`.

### 3. In the owner dashboard

1. **Booking settings:** set the real booking windows, group sizes, closed dates, then tick "I have reviewed
   these settings" and save.
2. **Team:** add employees. Each starts with **no permissions**. You get a one-time link for them to choose
   their own password; pass it on yourself (no email is sent). Then tick what they may do.
3. **Menu:** check the items marked "Please check".

## Upgrading an existing installation

Migration `0003` is additive and keeps existing data:

- Existing owner accounts are copied into the new `accounts` table with the **same email and password**.
- **Everyone signed in is signed out once** (sessions moved to a new table). Passwords are unchanged.
- Bookings, references, booking settings and menu rows are kept. Each existing booking gets one opening entry
  in the new status history.
- The old `owners` and `owner_sessions` tables are left in place, unused.

```bash
docker compose up -d --build        # runs `alembic upgrade head` on start
```

Do not edit migrations `0001`–`0003`; add new ones. This was rehearsed on a scratch database holding an
owner, bookings, menu edits and changed settings before being applied.

## Provisional booking settings

These demo values are seeded so the form works out of the box. **They are placeholders, not Wendy's hours.**

| Setting | Demo value |
|---|---|
| Booking windows | Every day, 8:00 AM to 6:00 PM (Pokhara time) |
| Group size | 1 to 8 guests |
| Minimum notice | 2 hours |
| How far ahead | 30 days |
| Time steps | 30 minutes |
| Confirmed by owner | No |

With `ENVIRONMENT=production` the API **refuses all booking requests** until the owner confirms the settings.
Only the owner can tick that confirmation.

## How reservations work

- A request is saved as `pending` with a server-generated reference. The customer sees: *"Your request has
  been received. Your table is not confirmed yet. The team will contact you after checking availability."*
- Staff check availability themselves and record the outcome. Status flow: `pending` → `confirmed`,
  `declined` or `cancelled`; `confirmed` → `checked_in`, `cancelled` or `no_show`; `checked_in` → `completed`.
- A customer's **cancellation request does not cancel anything by itself**. Staff accept or decline it and the
  customer sees the answer.
- If two staff act on the same booking at once, the second is told it changed and nothing is overwritten.
- A retried request never creates a duplicate; the same idempotency key with different details is a conflict.
- All dates and times are `Asia/Kathmandu`.

**Not tracked: tables, seats and booking length.** These are unconfirmed, so the system does not calculate
availability and never tells a guest a table is free. The dashboard says so.

**Notifications.** The dashboard checks for new pending requests every 20 seconds and shows an alert, with an
optional sound the user switches on. Customer pages refresh every 30 seconds. **No email, SMS or WhatsApp is
sent automatically.** WhatsApp buttons open a chat with a prepared message for a person to send.

## Employee permissions

Set per employee by the owner; checked by the server on every request, and applied from the employee's next
action (no new sign-in needed). Deactivating an employee signs them out at once.

`bookings.view_assigned`, `bookings.view_all`, `bookings.view_contact`, `bookings.approve`,
`bookings.decline`, `bookings.cancel`, `bookings.check_in`, `bookings.complete`, `bookings.mark_no_show`,
`bookings.edit_notes`, `menu.manage`, `booking_settings.manage`.

Without `bookings.view_contact`, guests' phone numbers and emails are left out of the server's responses, not
just hidden on screen. Employees cannot create accounts, grant permissions or change their own.

## Password reset and email

Set `EMAIL_DELIVERY` in `.env`:

| Value | Behaviour |
|---|---|
| `disabled` (default) | Nothing is sent. The "Forgot password" page says reset by email is not set up. |
| `dev_file` | **Development only.** Each email is written to `backend/dev-mailbox/` (git-ignored); nothing is sent. The API refuses to start with this in production. |
| `smtp` | Real delivery using `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`. |

Reset links are single-use, expire after 30 minutes, are stored only as hashes, and the answer is the same
whether or not the email has an account. The token is carried in the link's `#fragment`, which browsers do
not send to servers, so it does not appear in web-server logs. `PUBLIC_SITE_URL` must be the site's real address so links work.
SMTP delivery was not tested against a real mail server.

## Updating dependencies

**Backend.** `backend/requirements.in` and `requirements-dev.in` list what the project needs, as ranges.
`backend/requirements.txt` and `requirements-dev.txt` are **generated lockfiles**: every package, exact
version, with hashes. Docker builds install only from the lockfiles with `pip --require-hashes`, so a build
cannot pick up a different or altered release. To update, regenerate them inside the production base image
and review the diff:

```bash
docker run -d --name wendy-lock -v "$PWD/backend":/src:ro -w /work python:3.13-slim sleep 600
docker exec wendy-lock python -m pip install pip-tools
docker exec wendy-lock cp /src/requirements.in /src/requirements-dev.in /work/
docker exec wendy-lock pip-compile --generate-hashes --allow-unsafe --output-file=requirements.txt requirements.in
docker exec wendy-lock pip-compile --generate-hashes --allow-unsafe --output-file=requirements-dev.txt requirements-dev.in
docker cp wendy-lock:/work/requirements.txt backend/ && docker cp wendy-lock:/work/requirements-dev.txt backend/
docker rm -f wendy-lock
```

Then run the tests and check the new versions for advisories before committing.

**Frontend.** `frontend/package-lock.json` is the lockfile; Docker builds use `npm ci`. `package.json` has
one `overrides` entry that lifts a build-time CSS parser to its patched release.

## Tests

Tests run against a **separate, throwaway PostgreSQL database** (in memory) and build its schema through the
Alembic migrations. They never touch the development database.

```bash
docker compose --profile test run --rm tests
```

163 tests cover: registration cannot create privileged accounts; sign-in, sign-out, expired and revoked
sessions; CSRF and cross-site requests; customer A cannot read or change customer B's booking; guest bookings
are not claimed by matching contact details; every employee permission and contact-field filtering; immediate
effect of permission changes and deactivation; owner-only employee management; booking validation in Nepal
time, closed dates and special days; idempotent and simultaneous submissions; invalid and simultaneous status
changes; cancellation request and resolution; password reset; the repeatable menu import and owner edits; the
shared public/owner menu; rate limiting; server logs and admin command output free of customer data.

To run them outside Docker, point `TEST_DATABASE_URL` at a database whose name ends in `_test` (the suite
refuses anything else, because it drops and rebuilds the schema). Install the same locked packages the
containers use:

```bash
cd backend && python -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/wendy_test .venv/bin/python -m pytest -q
```

The lockfiles are generated for Python 3.13 on Linux (the container image). On another Python version or
operating system the hash check may refuse a package; use the Docker command above in that case.

## Project layout

```
backend/
  app/
    main.py             App, error format, cross-site write check, CORS
    config.py           Settings from environment variables
    models.py           Accounts, sessions, bookings, history, activity log, settings, menu
    permissions.py      Permission keys and the status rules
    schemas.py          Request/response validation
    security.py         Password hashing, sessions, role and permission guards
    booking_service.py  Booking rules, status changes, cancellation, response shaping
    menu_import.py      Repeatable import of the printed menu
    email_delivery.py   Email adapters (disabled / dev_file / smtp)
    rate_limit.py       Rate limiting stored in PostgreSQL
    cli.py              create-owner, set-password, import-menu, purge-rate-limits
    routers/            public.py, auth.py, customer.py, staff.py, owner.py
  data/menu_cm_pdf.json The printed menu, for import
  alembic/versions/     0001 schema, 0002 demo settings, 0003 accounts and workflow
  tests/
docker-compose.yml      Development stack
docker-compose.prod.yml Production stack (Caddy + API + PostgreSQL)
scripts/                backup.sh (encrypted), restore-rehearsal.sh
deploy/systemd/         Example timer and service for scheduled backups
brain/security/         Security audit, threat model, checklist and related notes
frontend/
  src/site/             Public pages
  src/auth/             Sign-in, registration, password pages
  src/customer/         Customer area
  src/staff/            Owner and employee dashboard
  src/lib/              API client, session, menu service, business details, helpers
  public/               Photos, logo, menu PDF
docs/
  API.md                Endpoint reference
  DEPLOYMENT.md         Production architecture, configuration and release steps
  OPERATIONS.md         Backups, recovery, monitoring, logs, proposed retention
  OWNER_CONFIRMATION.md Open questions and decisions for the owner
  ASSET_MANIFEST.md     Photos, menu and logo sources
```

## Security notes

- **Passwords:** Argon2id. No default accounts; secrets only in `.env` (git-ignored).
- **Sessions:** random token in an `HttpOnly`, `SameSite=Strict` cookie (`Secure` in production). Only a
  SHA-256 digest is stored, with an expiry (`SESSION_TTL_HOURS`). Sign-out, password change, password reset
  and deactivation revoke sessions.
- **CSRF:** every state-changing request needs the session's token in `X-CSRF-Token`; other origins are refused.
- **Access control:** enforced in the backend per endpoint and per object (a customer's queries are filtered
  by their own id; out-of-scope bookings are reported as not found).
- **Rate limits** are stored in PostgreSQL, so they hold across several API workers or instances sharing the
  database. Limits: sign-in 5 per 15 minutes per email from one address (and 50 per email overall, so one
  stranger cannot lock the owner out); registration 5 per hour, reset 5 per hour and guest bookings 5 per
  10 minutes per address. Behind a reverse proxy, set `TRUST_PROXY_HEADERS=true` so the
  visitor's address is used. Expired records are cleared automatically.
- **Privacy:** contact details, passwords and reset tokens are not written to logs. Unexpected errors are
  logged as a reference id, the error type and where it happened, never the error text (which can quote
  customer data); the same reference is returned to the client. The production database is configured not to
  echo failing statements or row values into its own log. Internal notes, history
  and the activity log are never returned to customers.
- Registration tells a visitor when an email is already registered. That is a deliberate usability choice,
  limited by the registration rate limit.

## Before going live

Nothing has been deployed. The deployment steps, production configuration and what was rehearsed are in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md); backups, recovery, monitoring, logs and a proposed data-retention
policy are in [docs/OPERATIONS.md](docs/OPERATIONS.md).

Still required: the owner's decisions in [docs/OWNER_CONFIRMATION.md](docs/OWNER_CONFIRMATION.md), a server
and domain, an email provider for password resets, off-server backups and monitoring.

Not verified: a real production host, real email delivery, browsers other than Chrome, screen readers, and
behaviour under heavy load.
