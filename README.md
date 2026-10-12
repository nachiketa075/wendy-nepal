# Wendy Juice Shop — website, table requests and owner dashboard

A website for Wendy Juice Shop (Lakeside, Pokhara) with a table-booking **request** flow and a protected owner
dashboard. It is a booking site only: there is no food ordering, cart, delivery or payment.

- **Frontend:** React, Vite, Tailwind CSS (`frontend/`)
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic (`backend/`)
- **Database:** PostgreSQL
- **Local development:** Docker Compose

> **Before real use**, read [docs/OWNER_CONFIRMATION.md](docs/OWNER_CONFIRMATION.md): the booking rules are
> provisional demo values and a few menu entries need the owner's answer.

## Current stage

The frontend has been updated with the shop's own photographs, its full printed menu, WhatsApp and three
sign-in pages. The backend is unchanged from the first version.

| Area | Status |
|---|---|
| Table requests (guest, no account) | Working, saved in PostgreSQL |
| Owner sign-in and dashboard (`/owner/login`, `/owner`) | Working |
| Public menu | Its own page at `/menu` (search and category filters), from the printed menu in `frontend/src/data/menuFromPdf.js`. The home page shows the menu sections and links there. |
| Owner menu editor | Works, but edits the **database** menu, which the website does not show yet |
| Customer sign-in (`/customer/login`) | Page only; sign-in is switched off |
| Staff sign-in (`/employee/login`) | Page only; sign-in is switched off |
| Customer, staff and team screens | Development-only design previews with fictional data |

What the backend stage must add is in [docs/API_HANDOFF.md](docs/API_HANDOFF.md).

## Run it locally

You need Docker with the Compose plugin.

```bash
cp .env.example .env
# Put a database password in .env. For example:
#   POSTGRES_PASSWORD=$(openssl rand -hex 24)
docker compose up --build
```

- Website: <http://localhost:5173>
- Owner dashboard: <http://localhost:5173/owner>
- API docs (development only): <http://localhost:8000/api/docs>

The backend applies the database migrations every time it starts. The first run also loads the demo booking
settings and the starting menu.

### Create the owner account

There is no default login and no sign-up page. Create the owner from the command line; you are prompted for a
password of at least 12 characters, which is stored only as an Argon2 hash.

```bash
docker compose exec backend python -m app.cli create-owner owner@example.com
```

To change it later (this also signs out every existing session):

```bash
docker compose exec backend python -m app.cli set-password owner@example.com
```

### Then, in the dashboard

1. Open **Booking settings**, set the real booking windows and group sizes, tick "I have reviewed these
   settings" and save.
2. The **Menu** tab edits the database menu. The public site currently shows the printed menu instead, so
   those edits are saved but not yet visible to guests (the tab says so).

### Frontend switches

Set these in `.env` (Docker Compose) or `frontend/.env.local` (running `npm run dev` yourself):

| Variable | Values | Meaning |
|---|---|---|
| `VITE_MENU_SOURCE` | `pdf` (default), `api` | Where the public menu comes from. No fallback between them. |
| `VITE_ENABLE_PREVIEW` | `false` (default), `true` | Shows the customer (`/customer`), staff (`/employee`) and owner "Team (preview)" design previews. Works only in the Vite dev server; production builds never include them. |

The previews use fictional data, keep everything in memory, call no API and store nothing in the browser. They
are not sign-ins and never show real bookings.

## Provisional demo settings

These are seeded by the second migration so the form works out of the box. **They are placeholders, not
Wendy's hours** — public listings disagree about opening times, so none of them were used.

| Setting | Demo value |
|---|---|
| Booking windows | Every day, 8:00 AM to 6:00 PM (Pokhara time) |
| Group size | 1 to 8 guests |
| Minimum notice | 2 hours |
| How far ahead | 30 days |
| Time steps | 30 minutes |
| Confirmed by owner | No |

With `ENVIRONMENT=development` the form accepts requests under these values so you can try it. With
`ENVIRONMENT=production` the API **refuses all booking requests** until the owner has confirmed the settings in
the dashboard; the site shows "Online table requests are paused" and the phone number instead.

## How booking works

- A guest sends a request: name, phone with country code, optional email, date, time, guests, optional notes.
- The backend validates it, stores it in PostgreSQL as `pending`, and generates the reference (for example
  `WJ-7KQ2MX`). The guest cannot set the status or reference; unknown fields are rejected.
- The guest sees: *"Your request has been received. Your table is not confirmed yet. The team will contact you
  after checking availability."* That message is only shown after the server confirms the request was saved.
- The owner confirms, declines or cancels it in the dashboard and can keep internal notes.

Things it deliberately does not do:

- **No notifications.** No email, SMS or WhatsApp is sent to anyone. Staff contact the guest themselves.
- **No capacity tracking.** The system does not know how many tables are free and will not stop the owner
  confirming overlapping requests. Checking availability is the owner's job, and the site never claims live
  availability.
- **No payments.**

All dates and times are in `Asia/Kathmandu`, whatever timezone the guest's device is in.

## Tests

The tests run against a real, throwaway PostgreSQL database and build its schema through the Alembic migrations.

```bash
docker compose --profile test run --rm tests
```

They cover booking validation (names, Nepali/Indian/international phone numbers, past dates and times judged in
Pokhara time, booking windows, group-size limits), persistence, server-set status and reference, duplicate
handling (same idempotency key, identical repeat request, four simultaneous submissions), rate limiting,
anonymous access to every owner route, forged and expired sessions, CSRF and cross-site origin checks, login,
status changes and their allowed transitions, settings and menu editing.

To run them outside Docker, point `TEST_DATABASE_URL` at a database whose name ends in `_test` (the suite
refuses anything else, because it drops and rebuilds the schema):

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/wendy_test .venv/bin/python -m pytest
```

## Project layout

```
backend/
  app/
    main.py             FastAPI app, error format, cross-site write check, CORS
    config.py           Settings from environment variables
    models.py           SQLAlchemy models
    schemas.py          Pydantic request/response validation
    booking_service.py  Booking business rules and status transitions
    security.py         Password hashing, sessions, owner + CSRF guard
    rate_limit.py       In-memory rate limiter
    cli.py              create-owner / set-password
    routers/            public.py, auth.py, owner.py
  alembic/versions/     0001 schema, 0002 demo settings + starting menu
  tests/
frontend/
  src/site/             Public page sections
  src/owner/            Owner dashboard (real session)
  src/auth/             Sign-in page layout; disabled customer/staff sign-in
  src/preview/          Development-only previews and their fictional data
  src/data/             The printed menu as structured data
  src/lib/              API client, menu service, business details, gallery list, time helpers
  public/images/        Display copies; public/images/original/ holds the supplied originals
  public/menu/          The printed menu PDF
docs/
  ASSET_MANIFEST.md     Every photo, the menu and the logo, with where they came from
  OWNER_CONFIRMATION.md What the owner still needs to confirm
  API_HANDOFF.md        Endpoints in use and the backend work still to do
```

## API summary

| Method and path | Who | Purpose |
|---|---|---|
| `GET /api/menu` | Public | Database menu (used by the site only when `VITE_MENU_SOURCE=api`) |
| `GET /api/booking/config` | Public | Booking rules for the form (no guest data) |
| `POST /api/bookings` | Public | Send a table request; returns reference, `pending`, message |
| `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` | Owner | Session |
| `GET /api/owner/bookings` (`status`, `date_from`, `date_to`) | Owner | List and filter requests |
| `GET`/`PATCH /api/owner/bookings/{id}` | Owner | Details; save internal notes |
| `POST /api/owner/bookings/{id}/status` | Owner | Confirm, decline or cancel |
| `GET`/`PUT /api/owner/settings` | Owner | Booking windows and limits |
| `GET /api/owner/menu`, `POST`/`PATCH`/`DELETE /api/owner/menu/items…`, `…/categories…` | Owner | Edit the menu |

There is no public endpoint that lists bookings or returns a guest's details.

## Security notes

- **Passwords:** Argon2id. No default account; nothing secret is committed. `.env` is git-ignored.
- **Sessions:** random token in an `HttpOnly`, `SameSite=Strict` cookie scoped to `/api` (`Secure` in
  production). Only a SHA-256 digest is stored, with an expiry (`SESSION_TTL_HOURS`).
- **CSRF:** every state-changing owner request must carry the session's token in `X-CSRF-Token`. Requests whose
  `Origin` is neither the site itself nor listed in `CORS_ORIGINS` are refused.
- **Authorisation:** the whole `/api/owner` router depends on the owner guard in the backend; the dashboard link
  not being in the site navigation is not what protects it.
- **Abuse limits:** booking requests 5 per 10 minutes and 30 per day per address; logins 5 per 15 minutes per
  email and 10 per address. The limiter is in memory, so it suits one API process; add a proxy-level limit if
  you run several.
- **Privacy:** guest contact details are never written to logs (only the booking reference is), owner responses
  are sent with `Cache-Control: no-store`, and the form carries a short privacy notice.

## Going to production (not done here)

This repository is set up for local development; nothing has been deployed. For a real deployment you would:

1. Set `ENVIRONMENT=production` and `CORS_ORIGINS=https://your-domain` (the API refuses to start in production
   with a wildcard, a non-HTTPS origin, or insecure cookies).
2. Build the frontend (`npm run build` in `frontend/`) and serve `frontend/dist` from a web server that also
   proxies `/api` to the backend, with HTTPS, and falls back to `index.html` for `/owner`.
3. Run the backend image without `--reload` (its default command) using `requirements.txt` only.
4. If the API is behind your own reverse proxy, set `TRUST_PROXY_HEADERS=true` so rate limits apply per visitor
   rather than to the proxy.
5. Use a managed or backed-up PostgreSQL, and decide how long guest details are kept.
6. Complete everything in [docs/OWNER_CONFIRMATION.md](docs/OWNER_CONFIRMATION.md).
