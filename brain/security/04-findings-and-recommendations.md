# Findings and recommendations

**Audited commit:** `834e59f26541e51977dcec21047423aa82f2c1a9` (branch `release/wendy-production-review`), 13 October 2026.

Severity reflects likely impact for a small café's booking site holding names, phone numbers and emails. It is
the auditor's judgement, not a formal score. "Evidence" states how each finding was established.

| ID | Severity | Title |
|---|---|---|
| F-01 | Medium | Database errors are logged with customer data |
| F-02 | Medium | Backend dependencies are not locked |
| F-03 | Medium | Backups are unencrypted and stay on the server |
| F-04 | Low–Medium | No Content-Security-Policy |
| F-05 | Low–Medium | No second factor for owner and staff |
| F-06 | Low | `react-router` version matches two advisories |
| F-07 | Low | Build-tool advisories (braces, postcss-selector-parser) |
| F-08 | Low | Outdated `pip` in the development environment |
| F-09 | Low | Public forms have no bot protection beyond rate limits |
| F-10 | Low | Free-text booking fields are shown to staff without contact permission |
| F-11 | Low | Visitor address logic assumes exactly one proxy |
| F-12 | Low | Sign-in attempts are not recorded |
| F-13 | Low | Password policy is length-only; registration reveals registered emails |
| F-14 | Low | Sessions have a fixed lifetime and no "sign out everywhere" for customers or the owner |
| F-15 | Informational | Requests without an `Origin` header pass the cross-site check |
| F-16 | Informational | Running the dev server directly listens on all network interfaces |
| F-17 | Informational | Database traffic is unencrypted (fine on one host only) |
| F-18 | Informational | Container base images are referenced by tag, not digest |

---

## F-01 — Database errors are logged with customer data (Medium)

**Where:** `backend/app/main.py:31-38` (`unexpected_error_handler`) logs every unhandled exception with its
traceback. `backend/app/database.py:15` creates the engine without `hide_parameters=True`.

**What:** SQLAlchemy includes the statement's bound values in the text of database exceptions. If any
unexpected database error occurs while saving or reading a booking or account, the log line contains the
values involved: names, email addresses, phone numbers, special requests, and password hashes on account
writes.

**Evidence:** Verified in code, and verified by an executed probe on a throwaway database: a deliberately
invalid insert produced an exception whose text contained the supplied email and name, and
`engine.hide_parameters` was `False`. Errors the application anticipates (`IntegrityError` in
`booking_service.py:184` and `routers/auth.py:114`) are caught and do not reach the log; the exposure is for
unanticipated failures (constraint violations elsewhere, connection drops mid-statement, deadlocks).

**Impact:** Personal data in container logs, which are retained (10 MB × 5 files per service) and are often
shipped to third-party log tools. It contradicts the project's own statement that contact details are not logged.

**Recommendation:** Pass `hide_parameters=True` to `create_engine`. Add a test that triggers a database
error and asserts the log contains no submitted values. Re-check before adding any error-tracking service.

## F-02 — Backend dependencies are not locked (Medium)

**Where:** `backend/requirements.txt` (version ranges; three packages without an upper bound),
`backend/Dockerfile:8-9` (installs from it at build time). There is no lockfile or hash file under `backend/`.

**What:** Each image build resolves whatever versions are current. The versions reviewed and tested here
(local environment, Python 3.14) are not necessarily those in a production image (Python 3.13, built later).

**Evidence:** Verified in code.

**Impact:** A release can silently include untested or newly vulnerable versions; builds are not reproducible;
a compromised upstream release would be pulled in without review.

**Recommendation:** Generate a fully pinned requirements file with hashes (for example `pip-compile
--generate-hashes` or `uv pip compile`) for the production Python version, install with `--require-hashes`,
and commit it. Run the advisory lookup against that file in CI.

## F-03 — Backups are unencrypted and stay on the server (Medium, operational)

**Where:** `scripts/backup.sh:11-17`. `docs/OPERATIONS.md` states that off-server copies are not set up.

**What:** The script writes a `pg_dump` file with owner-only permissions into `backups/` on the same machine.
It is not encrypted and nothing copies it elsewhere. The dump contains all customer data and password hashes.

**Evidence:** Verified in code. No deployment exists, so no real backup exposure exists yet.

**Impact:** Loss of the server loses the backups too; anyone who obtains a backup file reads all customer data.

**Recommendation:** Before launch: encrypt each dump (for example with `age` or `gpg` to a key kept off the
server), copy it to separate storage with restricted access, set a retention period, and alert when a backup
is missed. Keep rehearsing restores with `scripts/restore-rehearsal.sh`.

## F-04 — No Content-Security-Policy (Low–Medium)

**Where:** `frontend/Caddyfile:7-14` sets HSTS, `nosniff`, frame denial, referrer and permissions policies,
but no `Content-Security-Policy`.

**What:** No script injection was found (no raw HTML rendering in `frontend/src`; React escapes text). A CSP
is the safety net if one is introduced later, or a dependency is compromised. Without it, injected script
could act with a signed-in owner's session: the session cookie is `HttpOnly`, but the CSRF token is readable
by page script by design.

**Evidence:** Verified in code (header absent).

**Recommendation:** Add a policy such as `default-src 'self'; img-src 'self' data:; style-src 'self'
https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self'; frame-ancestors
'none'; base-uri 'self'; form-action 'self'; object-src 'none'`. Test it in report-only mode first; inline
styles used by components may need adjusting. Self-hosting the fonts allows a stricter policy and removes the
third-party request.

## F-05 — No second factor for owner and staff (Low–Medium)

**Where:** `backend/app/routers/auth.py:121-139` (`login`): password only.

**What:** The owner account can read every customer's contact details and manage staff. It is protected by a
password, rate limits and (when email is configured) an email-based reset.

**Evidence:** Verified in code (not implemented).

**Recommendation:** Add time-based one-time codes (TOTP) for the owner, optionally for staff. Until then: a
long unique password in a password manager, and protect the owner's email account with its own second factor.

## F-06 — `react-router` version matches two advisories (Low)

**Where:** `frontend/package-lock.json` (`react-router` and `react-router-dom` 6.30.6).

**What:** `npm audit` returns GHSA-wrjc-x8rr-h8h6 (open redirect via backslash in `<Link>`/`useNavigate`) and
GHSA-337j-9hxr-rhxg (constructor injection in SSR hydration). The installed version is inside both ranges.

**Evidence:** Version match verified from the lockfile and the advisory lookup. Reachability reviewed in code:
all navigation targets are constants or fixed lookups, and the app has no server-side rendering. No exploit
was attempted. Details in `03-dependency-review.md`.

**Recommendation:** Plan the upgrade to the fixed major version of `react-router-dom` and re-test routing.
Until then, do not introduce navigation to a destination taken from the URL or user input (for example a
`?next=` parameter).

## F-07 — Build-tool advisories (Low)

**Where:** `frontend/package-lock.json`: `braces` 3.0.3 (GHSA-vfj7-8cjw-p6xm), `postcss-selector-parser`
6.1.4 (GHSA-rj75-hqrm-r3gf), both development dependencies under `tailwindcss` 3.4.19.

**What:** Denial-of-service issues in tools that run only when the site is built, on the project's own files.
Not shipped to browsers.

**Evidence:** Version match verified from the lockfile and advisory lookup.

**Recommendation:** Upgrade when moving to the next Tailwind major version. Build only from trusted branches.

## F-08 — Outdated `pip` in the development environment (Low)

**Where:** Local `backend/.venv` (pip 25.1.1); not part of the repository.

**What:** OSV returns six advisories for that version, all about installing malicious packages.

**Evidence:** Version match verified by lookup. The production image's `pip` version is **Not verified**.

**Recommendation:** Upgrade `pip` locally and in the image build step. Hash-pinned installs (F-02) reduce the
exposure these advisories describe.

## F-09 — Public forms have no bot protection beyond rate limits (Low)

**Where:** `backend/app/routers/public.py:84-95` (guest booking: 5 per 10 minutes and 30 per day per
address); `backend/app/routers/auth.py:101-118` (registration: 5 per hour per address).

**What:** A distributed sender can fill the staff queue with plausible fake requests, or create many accounts.
Every booking is manually reviewed, so the harm is staff time and noise rather than a false confirmation.

**Evidence:** Verified in code. Limits verified by `test_bookings.py::test_booking_endpoint_is_rate_limited`.

**Recommendation:** Watch for it after launch. If it happens, add a challenge (for example a privacy-friendly
CAPTCHA) to the guest form, or require email or phone verification. A proxy-level request limit also helps.

## F-10 — Free-text fields reach staff without contact permission (Low)

**Where:** `backend/app/booking_service.py:423` (`special_requests`) and `:425` (`internal_notes`) in
`staff_view`.

**What:** Phone and email are withheld from staff lacking `bookings.view_contact`, but a guest may type a
phone number into "special requests", and a colleague may write one into internal notes. Both are returned to
anyone who can view the booking.

**Evidence:** Verified in code.

**Recommendation:** Tell staff not to put contact details in notes. Consider withholding `internal_notes`
from staff without `bookings.edit_notes`, and note on the form that special requests are visible to all staff.

## F-11 — Visitor address logic assumes exactly one proxy (Low)

**Where:** `backend/app/rate_limit.py:65-70` (`client_ip`); `docker-compose.prod.yml:21`.

**What:** With `TRUST_PROXY_HEADERS=true` the last `X-Forwarded-For` entry is used. That is correct with Caddy
alone in front. If a CDN or second proxy is added, every visitor appears as that proxy's address and
per-address limits become one shared limit. If the API were ever reachable directly, the header could be forged.

**Evidence:** Verified in code. Behaviour on a real topology is **Not verified**.

**Recommendation:** Document the rule next to the setting. If a CDN is added, configure a trusted-proxy count
or use the CDN's verified client-address header. Keep the API unreachable except through the proxy.

## F-12 — Sign-in attempts are not recorded (Low)

**Where:** `backend/app/routers/auth.py:121-139`. The activity log (`backend/app/activity.py`) records
password changes and staff actions but not sign-ins.

**What:** The owner cannot see failed or unusual sign-ins to their own or staff accounts.

**Evidence:** Verified in code.

**Recommendation:** Record successful and failed owner and staff sign-ins (time, account, coarse address) in
the activity log, subject to the retention decision.

## F-13 — Password policy and email disclosure at registration (Low)

**Where:** `backend/app/schemas.py:425` (length 12–256 only); `backend/app/routers/auth.py:106-108`
(registration answers that an email is already registered).

**What:** Common or breached 12-character passwords are accepted. Registration lets someone test whether an
email has an account, limited to 5 attempts per hour per address. Sign-in and reset do not disclose this.

**Evidence:** Verified in code; `test_accounts.py::test_duplicate_email_is_refused_case_insensitively`.

**Recommendation:** Consider a breached-password check at registration and password change. The disclosure is
a common usability trade-off; if unwanted, answer generically and email the address instead (needs email delivery).

## F-14 — Session lifetime and customer/owner session control (Low)

**Where:** `backend/app/config.py:19` (12-hour fixed lifetime); `backend/app/security.py:41-53`.

**What:** A session lasts 12 hours regardless of activity. Customers and the owner can end other sessions
only by changing their password; only employees can be signed out by someone else.

**Evidence:** Verified in code.

**Recommendation:** Acceptable for launch. Later, add "sign out of all devices" to the account page and
consider a shorter lifetime for staff on shared devices.

## F-15 — Requests without an `Origin` header pass the cross-site check (Informational)

**Where:** `backend/app/main.py:45-52`.

**What:** The check applies only when an `Origin` header is present, and compares host and port but not
scheme. Browsers send `Origin` on cross-site state-changing requests, and authenticated requests also need
the CSRF token, so no bypass was identified. Sign-in and registration rely on this check and `SameSite`.

**Evidence:** Verified in code.

**Recommendation:** None required. Optionally also check `Sec-Fetch-Site` and compare the scheme.

## F-16 — Dev server listens on all interfaces when run directly (Informational)

**Where:** `frontend/vite.config.js:11` (`host: true`).

**What:** Docker Compose publishes the dev server on localhost only (`docker-compose.yml:55`), but running
`npm run dev` directly exposes it, and through its proxy the local API, to the local network.

**Evidence:** Verified in code.

**Recommendation:** Development only. Use `host: 'localhost'` unless testing from a phone, and avoid running
it on untrusted networks.

## F-17 — Database traffic is unencrypted (Informational)

**Where:** `docker-compose.prod.yml:16` (connection string without TLS options).

**What:** Fine while the API and database share one host's private container network. Not acceptable if the
database moves to another host or a managed service.

**Evidence:** Verified in code.

**Recommendation:** If the database is ever remote, require TLS (`sslmode=verify-full`) and restrict its
network access.

## F-18 — Base images referenced by tag (Informational)

**Where:** `backend/Dockerfile:1`, `frontend/Dockerfile.prod:3`, `:10`, `docker-compose.prod.yml:31`.

**What:** Tags move, so two builds can differ, and image contents were not scanned in this audit.

**Evidence:** Verified in code. Image contents **Not verified**.

**Recommendation:** Pin images by digest, rebuild on a schedule for security updates, and scan images (for
example with Trivy or Grype) as part of a release.

---

## Suggested order of work

1. **Before any real customer data:** F-01 (one-line change plus a test), F-03 (backup encryption and
   off-server copy), F-02 (lock backend dependencies).
2. **Before or shortly after launch:** F-04 (CSP in report-only, then enforce), F-05 (second factor for the
   owner), F-12 (sign-in records).
3. **Scheduled maintenance:** F-06, F-07, F-08, F-18 (dependency and image updates), F-10, F-13, F-14.
4. **Only if the deployment changes:** F-11, F-17.

## Items that need a deployment to verify

These could not be assessed from the repository and should be checked once a server exists: TLS
configuration and certificate renewal, that only ports 80 and 443 are reachable, that the `Secure` cookie
and security headers are actually served, real email delivery and its sender authentication (SPF, DKIM),
log retention as configured on the host, backup storage and access, and monitoring alerts.

## Not security defects, recorded for completeness

- Opening hours, table capacity and booking duration are unconfirmed business facts; the system
  deliberately does not model availability.
- Guest-photo consent and the data-retention policy are open owner decisions (`docs/OWNER_CONFIRMATION.md`,
  `docs/OPERATIONS.md`).

---

## Status update — 13 October 2026 (remediation)

The findings above describe commit `834e59f26541e51977dcec21047423aa82f2c1a9` and are left as written. This
section records what changed afterwards. The changes are in the commits that follow the audited commit on
`release/wendy-production-review` (`git log 834e59f..release/wendy-production-review`). They have not been
pushed, merged or deployed.

| ID | Status now | What was done / what remains |
|---|---|---|
| F-01 | **Fixed in the application** (API server, database log settings, admin command line), verified by executed tests and real-process probes. Two conditions outside the code remain | See below |
| F-02 | **Fixed** (verified by a clean build) | See below |
| F-03 | **Partly fixed**: encryption done and tested; scheduling and off-server copies **NOT VERIFIED** | See below |
| F-04 | **Open**: policy written and validated in report-only mode; **not enforced** | See below |
| F-05 | **Open**: plan written, nothing implemented | `mfa-plan.md` |
| F-06 | **Open**: no compatible fix exists | `react-router` 6.30.6 is the newest 6.x release; the advisories are fixed only in 7.18.0+. Reachability unchanged: no user-controlled navigation target, no server-side rendering |
| F-07 | **Partly fixed** | `postcss-selector-parser` raised to 7.1.6 through an `overrides` entry (`frontend/package.json:23-25`); built CSS was byte-identical before and after. `braces` 3.0.3 remains: it is the latest release and no patched version exists |
| F-08 | **Fixed locally; not applicable to the image** | Local environment now has pip 26.2.1. The `python:3.13-slim` image used for the build contains pip 26.2.1, outside every advisory range returned |
| F-06, F-07 detail | | Exact advisory IDs, affected versions and applicability: `03-dependency-review.md`, "Remaining advisories in detail" |
| F-09 to F-18 | **Open, unchanged** | Not in scope of this round. Each is assessed for launch under "F-09 to F-18: launch assessment" below; none has been accepted on the owner's behalf |

### F-01 — what was found on a closer look, and what was changed

Reproduced with synthetic data on a disposable database, with a real server process running the audited
commit: one failing booking request produced server log lines containing the synthetic name, phone number,
email and note (two lines each, including a `[parameters: ...]` block).

There were **three** separate paths, not one:

1. **SQLAlchemy** appends bound values to exception text. Fixed with `hide_parameters=True`
   (`backend/app/database.py:24`).
2. **The catch-all handler re-raised.** Starlette runs an `Exception` handler and then re-raises, so the
   server (uvicorn) logged the full exception text regardless of what the handler logged. PostgreSQL also
   puts row values in the DETAIL of some errors (for example a duplicate key), which `hide_parameters` does
   not remove. Fixed by catching unexpected errors in the request middleware instead
   (`backend/app/main.py:60-68`, `_server_error` at `:32`) and logging through
   `backend/app/safe_logging.py`: a reference id, the exception type, the call sites, and for database errors
   the SQLSTATE and table/column/constraint names. The exception text is never logged. The reference id is
   returned to the client.
3. **PostgreSQL's own log** recorded the failing statement and values. Addressed in
   `docker-compose.prod.yml:39` (`log_min_error_statement=panic`, `log_error_verbosity=terse`).

**Evidence.** `backend/tests/test_logging.py` (5 tests, executed, passing) captures every logger at DEBUG and
asserts synthetic values are absent for a real database error, for a PostgreSQL DETAIL carrying an email, and
for a non-database exception whose message contains customer data; it also asserts the diagnostics are
present and that ordinary 401/404/422 answers are unaffected. With a real server process on a disposable
database, the same request produced zero log lines containing the values after the fix. On a throwaway
production stack, API, proxy and database logs contained none of the synthetic customer values after a full
booking flow.

4. **The admin command line** (`python -m app.cli`) printed a full Python traceback for any unexpected error.
   Reproduced on the audited commit with a real process: an unreachable database produced 122 lines of
   traceback including the database host and port. A duplicate-key error carries PostgreSQL's DETAIL, which
   quotes the email (this second case was triggered in the regression test, not reproduced on the audited
   commit). Fixed in `backend/app/cli.py:46-75` (`_failure_message`, `main`): unexpected errors now
   print a reference, a plain-language hint chosen from the database error class, and the same safe
   description the API logs (error type, SQLSTATE, table and constraint names, call sites). Problems with the
   menu file itself (missing file, invalid content) still print their own message, because that text
   describes the file, not customers (`cli.py:101-105`).

   Evidence: `backend/tests/test_cli.py` (6 tests, executed, passing) forces a real duplicate-key error on
   the accounts table and asserts the output contains no email, name, password or password hash, no
   traceback and no DETAIL, and does contain the error class, table, constraint and location. It also covers
   an unreachable database (no connection string in the output), a non-database error, menu-file errors and
   a normal run. With a real process, the fixed command printed 3 lines and no host, port or password.

**What F-01 does not cover (conditions outside the code, still open):**

- If the database is moved to a managed service, the two database log settings in
  `docker-compose.prod.yml:39` do not travel with it and must be set there. **Not verified on any real
  deployment.**
- Any future error-tracking or log-shipping service must be configured not to collect exception messages or
  request bodies. None is configured today.
- Expected command-line messages still show the email address the operator typed (for example "Owner account
  created for ..."). That is the operator's own input on their own terminal and was left as is.
- Alembic migration errors (`alembic upgrade head`) are not routed through this code and print normally.
  Current migrations change structure and fixed settings only; a future data migration that touches customer
  rows could print row values on failure.

### F-02 — what was changed

`backend/requirements.in` and `requirements-dev.in` now hold the ranges; `backend/requirements.txt` and
`requirements-dev.txt` are generated lockfiles (pip-tools 7.6.2, inside `python:3.13-slim`, Python 3.13.16)
with every package pinned and hashed. `backend/Dockerfile:12` installs with `--require-hashes`.
`uvicorn[standard]` was replaced by `uvicorn` plus `uvloop` and `httptools`, removing the unused `websockets`,
`watchfiles` and `PyYAML`.

**Evidence.** A `--no-cache` build was inspected: 33 packages installed (excluding pip), identical to the 33
pins in the lockfile; no test tools present; an unpinned install was refused by pip. All 41 pins across both
lockfiles were looked up in OSV on 13 Oct 2026: no advisories.

### F-03 — what was changed, and what is not verified

`scripts/backup.sh` now encrypts the dump to a public key as it is produced (`:53`), refuses to run without a
key, writes a checksum, optionally copies off-server with rclone, and can prune old local files.
`scripts/restore-rehearsal.sh` verifies the checksum and decrypts in memory. Example systemd units are in
`deploy/systemd/`; settings template in `.env.backup.example` (no secrets).

**Evidence (synthetic data, disposable database, throwaway key pair):** encrypted file written with private
permissions and no private key on the "server" side; restored with matching rows; decryption failed without
the private key; a modified file was rejected by its checksum; with no key configured nothing was written;
pruning removed only old backup files.

**NOT VERIFIED:** off-server delivery (rclone was not installed and no storage exists; only the failure
message was observed), scheduled operation (the systemd units have never been installed), and restoring onto
a real server. **No backups are running anywhere.**

### F-04 — what was changed, and what is not claimed

A policy was derived from an inventory of the built site (one script bundle and chunks from the same origin,
one stylesheet, Google Fonts, same-origin images plus a data: favicon, same-origin API calls, no frames,
workers, `eval` or inline scripts) and added to `frontend/Caddyfile:22` as
**`Content-Security-Policy-Report-Only`**.

**Evidence.** On a throwaway production stack, a browser run across 13 pages and the main customer, employee
and owner flows reported zero violations. Deliberate violations (inline script, external image, external
fetch) were reported, showing the policy is being evaluated.

**Not claimed:** browsers do not block anything under a report-only policy. In the same run the deliberately
injected inline script still executed. F-04 stays open until the header is switched to
`Content-Security-Policy` after observation on the live site. There is no report collector; violations are
visible only in a browser console.

---

## F-09 to F-18: launch assessment (13 October 2026)

These ten findings were **not changed** in this round. The table below is a recommendation only. "Blocks
launch?" is the reviewer's view of whether the site should take real customers' data with the item as it is;
**the decision on each one belongs to the owner and none has been accepted on the owner's behalf.** Line
numbers refer to the current tree. Evidence is from reading the code unless a test is named; none of these
was tested by attack.

| ID | Severity | Evidence | Risk that remains if launched as is | Blocks launch? |
|---|---|---|---|---|
| F-09 | Low | `routers/public.py:89-90` (guest booking: 5 per 10 min, 30 per day per address); `routers/auth.py:104` (registration: 5 per hour per address). Limits covered by `test_bookings.py::test_booking_endpoint_is_rate_limited`. No challenge of any kind | Someone using many addresses can fill the staff queue with fake requests or create many accounts. Cost is staff time; no booking is confirmed without a person approving it. Nothing would alert anyone that it is happening | **No**, on condition someone looks at the queue daily. Needs an owner decision on what to do if it happens |
| F-10 | Low | `booking_service.py:423,425` returns `special_requests` and `internal_notes` to anyone who can view the booking, including staff without `bookings.view_contact` | A guest who types a phone number into "special requests", or a colleague who writes one in a note, defeats the contact-permission restriction for that booking | **No**, but it weakens a control the owner may be relying on. If any employee is to be denied contact details, tell the owner this gap exists before they rely on it |
| F-11 | Low | `rate_limit.py:65-70` takes the last `X-Forwarded-For` entry; `docker-compose.prod.yml:21` turns it on. Correct only with exactly one proxy (Caddy). **Not verified on a real network** | Behind a CDN or load balancer every visitor shares one address: a few people booking would lock everyone out, and the per-address sign-in limits stop meaning anything | **Conditional. Blocks launch if** the hosting puts anything in front of Caddy (CDN, load balancer, platform proxy). Does not block a single server with Caddy facing the internet. Cannot be closed until hosting is chosen |
| F-12 | Low | `routers/auth.py:121-139` (`login`) writes nothing to the activity log; `activity.py` records password changes and staff actions only | A stolen or guessed staff password would be used without leaving a trace the owner can see. Combined with F-05 (no second factor), the owner account has no detection at all | **No** by itself. **Recommended before launch together with F-05**, because the two together leave the owner account protected by one password with no way to notice misuse |
| F-13 | Low | `schemas.py` password rule is length only (12 to 256); `routers/auth.py:106-108` answers "already exists" at registration. Covered by `test_accounts.py::test_duplicate_email_is_refused_case_insensitively` | Weak but long passwords are accepted. Anyone can check whether an email has an account, 5 tries per hour per address | **No.** Owner should know registration reveals who has an account |
| F-14 | Low | `config.py:19` (12-hour fixed session); `security.py` session creation and revocation | A session left open on a shared shop device stays usable for up to 12 hours. Customers and the owner can end other sessions only by changing their password | **No**, if staff are told to sign out on shared devices |
| F-15 | Informational | `main.py:54-60`: the origin check runs only when an `Origin` header is present and ignores the scheme | No bypass was found: signed-in requests also need the CSRF token, and the cookie is `SameSite=Strict`. Sign-in and registration rely on this check and the cookie setting alone | **No** |
| F-16 | Informational | `frontend/vite.config.js:11` (`host: true`). Docker Compose publishes on localhost only | Development only. Running `npm run dev` directly on shared Wi-Fi exposes the dev site and local API to that network | **No** (not part of production) |
| F-17 | Informational | `docker-compose.prod.yml:16`: connection string has no TLS options | None while the API and database share one host's private network. Customer data would cross the network unencrypted if the database moved elsewhere | **Conditional. Blocks launch if** the database is on another host or a managed service. Not otherwise |
| F-18 | Informational | `backend/Dockerfile:1`, `frontend/Dockerfile.prod:3,10`, `docker-compose.prod.yml:31` use tags. **Image contents were never scanned** | Two builds can differ, and known flaws in the base images' system packages are unknown rather than absent | **No**, but an image scan before launch is cheap and is the only way to answer what is in them |

**Summary.** None of F-09 to F-18 is recommended as an unconditional blocker. Two depend on hosting choices
not yet made (F-11, F-17) and must be re-checked once they are. F-12 is recommended alongside F-05. The rest
are risks for the owner to accept knowingly or schedule; until the owner has done so they remain **open, not
accepted**.

This table does not make the site ready to launch. The items that block launch are listed in
`security-checklist.md` and include F-03 (no backups running), F-04 (policy not enforced), F-05 (owner
decision), and all deployment work.
