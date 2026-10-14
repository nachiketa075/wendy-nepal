# Security checklist

**Baseline:** commit `834e59f26541e51977dcec21047423aa82f2c1a9` (the audited commit) on `release/wendy-production-review`, plus the remediation changes of 13 October 2026 described in `04-findings-and-recommendations.md` ("Status update"), committed after it on the same branch (`git log 834e59f..release/wendy-production-review`). Entries marked "added 14 Oct 2026" describe the staff inventory feature, committed after that on the same branch.

Status key: **Done** = implemented; "(test)" means an automated test covering it was run and passed on
13 October 2026, "(code)" means it was read in the source only. **Open** = an unresolved finding.
**Pending** = can only be done or checked on a real deployment. **Owner** = needs an owner decision.

Passing tests show the tested cases behave as intended; they do not prove the absence of other flaws.

## A. Application controls

| # | Item | Status | Evidence / finding |
|---|---|---|---|
| A1 | Passwords hashed with Argon2id | Done (test) | `backend/app/security.py:26` |
| A2 | Uniform sign-in failure; no account enumeration at sign-in or reset | Done (test) | `routers/auth.py:137-138`, `:182-207` |
| A3 | Registration always creates a customer | Done (test) | `routers/auth.py:109` |
| A4 | Owner created only by server command; employees only by the owner | Done (test) | `cli.py:116`; `routers/owner.py:59` |
| A5 | Session cookie HttpOnly, SameSite=Strict, Secure in production | Done (test) | `routers/auth.py:64-72`; `config.py:71-74` |
| A6 | Session tokens stored as digests; expiry and revocation enforced | Done (test) | `security.py:41-72` |
| A7 | CSRF token and origin check on state-changing requests | Done (test) | `security.py:75-84`; `main.py:51` |
| A8 | Role and permissions enforced server-side on every staff and owner route | Done (test) | `routers/staff.py:42`; `routers/owner.py:22` |
| A9 | Per-action employee permissions; default none | Done (test) | `permissions.py`; `booking_service.py:263` |
| A10 | Permission removal, deactivation and session revocation apply immediately | Done (test) | `security.py:70`; `routers/owner.py:95-123` |
| A11 | Customers reach only their own bookings | Done (test) | `routers/customer.py:43`, `:63` |
| A12 | Contact details withheld from staff without permission | Done (test) | `booking_service.py:398`, `:418-419` |
| A13 | Free-text fields cannot carry contact details to restricted staff | Open | F-10 |
| A14 | Bookings always start pending; server sets status and reference | Done (test) | `booking_service.py:142-175` |
| A15 | Idempotent submissions; concurrent staff changes cannot overwrite | Done (test) | `booking_service.py:112-139`, `:208-227` |
| A16 | Reset and setup tokens: random, hashed, expiring, single-use, in URL fragment | Done (test) | `routers/auth.py:77-93`, `:210-223` |
| A17 | No email delivery is claimed unless configured; dev email mode refused in production | Done (test) | `routers/auth.py:188-190`; `config.py:56-57` |
| A18 | Rate limits on sign-in, registration, reset, booking; shared through the database | Done (test for sign-in and booking; code for the rest) | `rate_limit.py`; multi-worker behaviour not tested |
| A19 | Unknown request fields rejected; inputs validated and length-capped | Done (test) | `schemas.py:19-21` |
| A20 | Parameterised SQL only | Done (code) | Reviewed `backend/app/` |
| A21 | No raw-HTML rendering in the frontend | Done (code) | Searched `frontend/src` |
| A22 | Unexpected errors logged without customer data, with a reference id | Done (test) — **F-01 fixed** | `safe_logging.py`; `main.py:32-68`; `database.py:24`; `cli.py:46-75`; `tests/test_logging.py`, `tests/test_cli.py` |
| A23 | Client error responses carry no internals | Done (test) | `main.py:32-47` |
| A24 | API responses not cacheable | Done (test) | `main.py` (Cache-Control default) |
| A25 | Activity log of staff and owner actions | Done (test) | `activity.py` |
| A26 | Sign-in attempts recorded | Open | F-12 |
| A27 | Second factor for owner and staff | Open (plan written) | F-05; `mfa-plan.md` |
| A28 | Breached-password check; registration email disclosure | Open | F-13 |
| A29 | "Sign out everywhere" for customers and owner; idle timeout | Open | F-14 |
| A30 | Bot protection on public forms | Open | F-09 |
| A31 | Inventory reachable only with `inventory.view`; writes need their own permission (added 14 Oct 2026) | Done (test, browser) | `routers/inventory.py:32-47`; `tests/test_inventory.py` |
| A32 | Inventory permissions granted to nobody by default; dependency enforced | Done (test) | `permissions.py:26`; `routers/owner.py:47`; migration `0004` touches no account |
| A33 | Stock entries atomic, locked, idempotent; no negative stock | Done (test) | `inventory_service.py:93`, `:101`, `:202`; database checks in `0004` |
| A34 | Stock history append-only; actor from the session | Done (test) | Trigger in `0004`; `inventory_service.py` `_movement` |
| A35 | Inventory kept out of public responses | Done (test) | `test_inventory_never_appears_in_public_responses` |

## B. Build and dependencies

| # | Item | Status | Evidence / finding |
|---|---|---|---|
| B1 | Backend dependencies locked with hashes; image installs only from the lockfile | Done — **F-02 fixed** | `backend/requirements.txt`; `backend/Dockerfile:12`. A clean build's packages matched the lockfile exactly |
| B2 | Frontend built from its lockfile | Done (code) | `frontend/Dockerfile.prod` (`npm ci`) |
| B3 | Backend packages free of known advisories | Done on 13 Oct 2026 | OSV lookup of all 41 pins: none. Must be repeated regularly |
| B4 | `postcss-selector-parser` advisory | Done | Overridden to 7.1.6 (`frontend/package.json:23-25`); built CSS byte-identical |
| B5 | `react-router` advisories | Open | F-06: no patched 6.x release exists; fix is a major upgrade. No exploitable path found in this app |
| B6 | `braces` advisory (build tool) | Open | F-07: no patched release exists (3.0.3 is the latest). Build-time only |
| B7 | Base images pinned by digest and scanned | Open | F-18 |
| B8 | Advisory lookup automated in CI | Open | No CI exists |

## C. Deployment configuration (prepared in the repository)

| # | Item | Status | Evidence / finding |
|---|---|---|---|
| C1 | Only the proxy publishes ports | Done (code) | `docker-compose.prod.yml` |
| C2 | API runs as non-root, no reload, migrations as a release step | Done (code); observed on a throwaway stack, including an upgrade release on 14 Oct 2026 | `backend/Dockerfile`; `docker-compose.prod.yml`. The migrate step ran a stale image on every release after the first; fixed 14 Oct 2026 (shared `wendy-backend:release` image) |
| C3 | Production refuses wildcard/non-HTTPS origins, insecure cookies, dev email mode | Done (test) | `config.py:47-64` |
| C4 | HSTS, nosniff, frame denial, referrer policy | Done (code); observed on a throwaway stack | `frontend/Caddyfile` |
| C5 | Content Security Policy **enforced** | **Open** — report-only | F-04. Policy validated with zero violations across main flows, and again on 14 Oct 2026 across the inventory, team and booking flows; browsers do not block under report-only |
| C6 | Database log does not echo statements or row values | Done (code); observed on a throwaway stack | `docker-compose.prod.yml:39` |
| C7 | Request body size cap | Done (code); observed (413) on a throwaway stack | `frontend/Caddyfile` |
| C8 | Backups encrypted before reaching disk; server holds no private key | Done; tested with synthetic data — **F-03 encryption fixed** | `scripts/backup.sh` |
| C9 | Restore procedure rehearsed | Done with synthetic data on a disposable database | `scripts/restore-rehearsal.sh` |

## D. Pending: needs a real deployment

| # | Item | Status |
|---|---|---|
| D1 | Server, domain and DNS chosen and set up | Pending / Owner |
| D2 | From outside: only ports 80 and 443 answer; SSH restricted to keys | Pending |
| D3 | Valid certificate served; HTTP redirects; headers present on the live site | Pending |
| D4 | `.env.production` created with fresh secrets, mode 600, not in git | Pending |
| D5 | Backup key pair generated off the server; private key stored in two safe places | Pending / Owner |
| D6 | **Backups scheduled** | **NOT VERIFIED — no schedule exists** |
| D7 | **Backups copied off the server** | **NOT VERIFIED — no storage configured** |
| D8 | First real backup restored in a rehearsal | Pending |
| D9 | Uptime and backup-age monitoring with alerts | Pending |
| D10 | SMTP configured and a reset email received in a real inbox; SPF/DKIM set | Pending |
| D11 | CSP switched from report-only to enforcing after observation | Pending |
| D12 | Owner account created; booking rules confirmed; staff added with least privilege | Pending / Owner |
| D13 | Rate limiting sees real visitor addresses behind the proxy | Pending (F-11) |

## E. Owner decisions

| # | Item |
|---|---|
| E1 | Approve a data-retention policy (proposal in `docs/OPERATIONS.md`); nothing is deleted today |
| E2 | Confirm consent for identifiable guests in the published photos |
| E3 | Decide when staff second-factor sign-in is built (`mfa-plan.md`) |
| E4 | Accept or change: registration reveals registered emails; fonts loaded from Google |
| E5 | Publish a privacy notice |
| E6 | Decide which employees get inventory access, and whether recording stock should also allow editing items |

## F. Before each release

- [ ] Tests pass on a throwaway database (`docker compose --profile test run --rm tests`)
- [ ] Frontend builds (`npm run build`)
- [ ] `npm audit` and an OSV lookup of `backend/requirements.txt` reviewed
- [ ] Encrypted backup taken and its checksum verified
- [ ] Migrations reviewed; a recovery path written down for any that change existing data
- [ ] `/api/ready` returns ready after the release
- [ ] No secrets, dumps or logs in the diff
