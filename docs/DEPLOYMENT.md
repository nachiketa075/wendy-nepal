# Deployment handoff

Status: **prepared and rehearsed locally, not deployed.** No server, domain or email provider has been
chosen. Nothing here has been run against a real host.

## Architecture

One server (or VM) running three containers from `docker-compose.prod.yml`:

```
Internet ──HTTPS──> Caddy (ports 80/443)
                      ├── serves the built React site
                      └── /api/* ──> FastAPI (private) ──> PostgreSQL (private, named volume)
```

- **One public origin.** The site and `/api` share the same address, so the session cookie is first-party
  (`SameSite=Strict`) and no cross-origin setup is needed.
- **Only Caddy publishes ports.** The API and database are reachable only inside the Compose network.
- **HTTPS** certificates are obtained and renewed by Caddy once the domain's DNS points at the server.
- **The API runs without reload**, as a non-root user, with 2 workers, on dependencies installed from a
  hash-pinned lockfile. Rate limits live in PostgreSQL, so
  they hold across workers.
- **Migrations are a release step**, not run at start-up. The API reports "not ready" until they are applied.

### Is a single origin required?

No. It is the simplest safe option, not a technical necessity. Two alternatives:

- **Frontend on a static host (for example the existing Vercel project), API elsewhere, joined by a proxy
  rule.** Add a rewrite on the static host that forwards `/api/*` to the backend. The browser still sees one
  origin, so nothing in the app changes. The backend must then trust that proxy for the visitor address
  (`TRUST_PROXY_HEADERS=true`), and should accept traffic only from it.
- **True cross-origin (site on one domain, API on another).** This needs code changes that are not made:
  the cookie would have to be `SameSite=None; Secure`, the frontend would need the API's full address, and
  `CORS_ORIGINS` must list the site. Browsers that block third-party cookies would break sign-in unless
  both are subdomains of one registrable domain. Not recommended.

**The current Vercel project serves only the frontend.** Since the menu and all accounts now come from the
API, merging this branch to `main` would publish a site there whose menu, booking form and sign-in show
errors until an API is reachable at `/api`. Decide the hosting before merging.

## What you need first

| Needed | Why |
|---|---|
| A server with Docker (1 vCPU / 1–2 GB RAM is enough to start), ports 80 and 443 open | Runs the stack |
| A domain name, with an A/AAAA record pointing at the server | HTTPS and the public address |
| An SMTP account (any transactional email provider) | Password-reset emails. Optional at launch: without it the site says reset by email is unavailable |
| An off-server place for backups | See `OPERATIONS.md` |

## Configuration

On the server, in the project folder:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

| Variable | Set to |
|---|---|
| `SITE_ADDRESS` | The host name only, for example `wendyjuice.example` |
| `PUBLIC_SITE_URL` | The same site with `https://`, for example `https://wendyjuice.example`. Used as the allowed origin and in reset/setup links. **Not** a localhost address |
| `POSTGRES_PASSWORD` | `openssl rand -hex 32` |
| `.env.backup` (separate file) | Backup settings; see `docs/OPERATIONS.md`. Holds a path to a **public** key only |
| `EMAIL_DELIVERY` | `disabled`, or `smtp` with the `SMTP_*` values filled in |

The API refuses to start in production if the origin is a wildcard or not HTTPS, if `PUBLIC_SITE_URL` is not
HTTPS, if cookies are set insecure, or if a development email mode is selected. Development keeps its own
`.env` (which may point at `localhost`); the two files are separate and neither is committed.

Throughout, `dc` means:

```bash
alias dc='docker compose -f docker-compose.prod.yml --env-file .env.production'
```

## First deployment

```bash
git clone https://github.com/nachiketa075/wendy-nepal.git && cd wendy-nepal
git checkout <the reviewed commit or tag>
# create .env.production as above

dc build
dc up -d db
dc run --rm migrate                      # release step: applies migrations
dc up -d                                 # API + Caddy

curl -fsS https://YOUR-DOMAIN/api/ready  # {"status":"ready"}

dc exec backend python -m app.cli create-owner OWNER-EMAIL --name "Owner Name"
dc exec backend python -m app.cli import-menu                        # dry run, read the summary
dc exec backend python -m app.cli import-menu --apply --hide-legacy
```

Then, signed in as the owner at `/owner/login`:

1. **Booking settings**: enter the real windows, group sizes and closed dates, tick "I have reviewed these
   settings", save. Until this is done the public form says requests are paused.
2. **Team**: add employees and their permissions; pass each their one-time link.
3. **Menu**: resolve the items marked "Please check".
4. Send one real test request from a phone, confirm it, and check it under the customer's "My bookings".
5. Set up encrypted backups: key pair, off-server copy and schedule, then take the first backup and rehearse
   a restore (`OPERATIONS.md`). Until that is done and checked, there are no backups.

## Releasing a new version

```bash
scripts/backup.sh                        # always, before a release
git fetch && git checkout <new commit or tag>
dc build
dc run --rm migrate                      # only does something if there are new migrations
dc up -d                                 # replaces API and Caddy; the database volume is untouched
curl -fsS https://YOUR-DOMAIN/api/ready
```

`dc run --rm migrate` runs the image that `dc build` just built for the API (`wendy-backend:release`). Until
14 Oct 2026 the migrate service had its own build, which `dc build` skipped because of its profile: on any
release after the first, the step ran the **previous** version's migrations and changed nothing (the API then
stayed "not ready"). Found and fixed during the inventory release rehearsal.

When adding a migration, also update `EXPECTED_REVISION` in `backend/app/routers/public.py`, so the
readiness check knows the schema the code expects.

## Content Security Policy: report-only for now

`frontend/Caddyfile` sends `Content-Security-Policy-Report-Only`. **Browsers do not block anything under a
report-only policy**; they only note violations in the browser console. It was validated on 13 Oct 2026
against the main customer, staff and owner flows on a local throwaway stack with no violations.

To enforce it after launch:

1. Use the live site normally for a week or two with the browser console open on a few visits (public
   pages, booking, sign-in, dashboard). There is no report collector, so violations are visible only there.
2. If none appear, rename the header in `frontend/Caddyfile` to `Content-Security-Policy`, rebuild and
   release (`dc build web && dc up -d web`).
3. Re-check the same flows. To go back, rename the header again.

If a new external resource is ever added (a map embed, analytics, another font host), add it to the policy first.

## Checks

| Address | Meaning |
|---|---|
| `GET /api/health` | The API process is running. No database access |
| `GET /api/ready` | Database reachable **and** migrated to the expected version. `503` with `unavailable` or `migration_pending` otherwise. Never returns connection details |

The backend container's own health check uses `/api/ready`.

## What was rehearsed locally (12 Oct 2026)

On a throwaway copy of this stack at `https://localhost:8443` with a self-signed certificate:

- Build of both images; API "not ready" before the migration step and "ready" after it.
- Only Caddy's ports published; API running as a non-root user with no reload.
- Page addresses (`/menu`, `/owner/login`, `/customer/register`…) load on refresh; photos, logo and menu PDF load.
- HTTP redirects to HTTPS; security headers present; API docs return 404; oversized request bodies refused.
- Session cookie is `HttpOnly; Secure; SameSite=Strict`; a foreign `Origin` is refused.
- Booking refused until the owner confirmed the rules; then the full flow in a browser: registration, a
  request (three clicks produced one), employee confirmation without contact details, customer sees
  "Confirmed", cancellation request and resolution, permission removal, session revocation, deactivation.
- No setup token, phone number or password appeared in the proxy or API logs.
- Data survived replacing all containers; the API stopped cleanly in about a second.
- A backup was taken and restored into a disposable database with matching row counts.

### Inventory release rehearsal (14 Oct 2026)

On a throwaway copy of the production stack (`https://localhost:8443`, self-signed certificate), with
synthetic data only:

- Started at the previous release (migration `0003`) with an owner, an employee with booking permissions,
  the imported menu, confirmed booking rules and a guest booking. Then built the inventory version and
  started it **without** migrating: `/api/ready` answered `503` and the schema stayed at `0003`. The separate
  `migrate` step then applied `0003 → 0004`; the API became ready. Accounts, the employee's permissions
  (no inventory added), the booking and 104 menu items were unchanged; inventory was empty.
- 49 browser checks in Chrome passed, desktop and phone: owner inventory flows (add, stock in/out,
  correction with reason, refused overselling, edit without stock change, locked unit, whole pieces,
  search/category/low-stock filters, history); a restricted employee (view and record stock only) and
  immediate revocation; customer `403` and visitor `401`; the pre-upgrade employee keeping bookings and
  getting no inventory; a guest booking and the owner confirming it.
- **Failure injection:** a stock entry reached the server and was recorded, but the browser's connection was
  dropped before the reply. The page said the outcome was unknown and that pressing again is safe; pressing
  again showed the entry once, and exactly one movement exists.
- **Content Security Policy (report-only):** zero violations across all of the above; a deliberately
  injected external image was reported, so the policy was being evaluated. Not enforced.
- Encrypted backup and restore rehearsal with inventory data: see `OPERATIONS.md`.
- Proxy, API and database logs contained none of the synthetic phone numbers, emails, names, stock reasons or
  setup tokens.

**Not rehearsed:** a real server, a real domain and certificate, real email delivery, restoring onto the
production host, load beyond a few simultaneous requests.
