# Dependency review

**Audited commit:** `834e59f26541e51977dcec21047423aa82f2c1a9` (branch `release/wendy-production-review`), 13 October 2026.

Advisory lookups were made on 13 October 2026 with `npm audit` (npm registry advisory database) and the OSV
API (`api.osv.dev`). Both were reachable. A vulnerability is listed below only where the lookup returned an
advisory **and** the installed version falls inside the advisory's affected range. Advisory titles and ranges
are quoted as returned by those services; they were not independently re-derived.

## 1. What was examined

| Component | Manifest | Lockfile | Versions examined |
|---|---|---|---|
| Frontend | `frontend/package.json` | `frontend/package-lock.json` (lockfileVersion 3, 184 packages) | The lockfile. `npm ls` confirmed the installed tree matches it |
| Backend | `backend/requirements.txt`, `backend/requirements-dev.txt` | **None** | The packages installed in the local development environment `backend/.venv` (Python 3.14.4), 45 packages |
| Container base images | `backend/Dockerfile:1`, `frontend/Dockerfile.prod:3`, `:10`, `docker-compose.prod.yml:31` | n/a | Tags only: `python:3.13-slim`, `node:22-alpine`, `caddy:2-alpine`, `postgres:18` |

**Important limit.** The backend has no lockfile and `requirements.txt` uses version ranges. The production
image is built on Python 3.13 and resolves versions at build time, so the versions inside a production image
may differ from those reviewed here. **The production image's actual package versions are Not verified.**
Base images were not scanned; their contents are **Not verified**. See findings F-02 and F-18.

## 2. Frontend — packages shipped to visitors' browsers

| Package | Locked version |
|---|---|
| react | 18.3.1 |
| react-dom | 18.3.1 |
| react-router-dom | 6.30.6 |
| react-router | 6.30.6 |
| @remix-run/router | 1.23.4 |

### Advisory matches

| Package | Installed | Advisory | Affected range (per advisory) | Severity (npm) | Reachability in this application |
|---|---|---|---|---|---|
| react-router (via react-router-dom) | 6.30.6 | GHSA-wrjc-x8rr-h8h6 — open redirect via backslash in `<Link>` and `useNavigate` | `>=6.0.0 <7.18.0` | Moderate | Version matches. Every `<Link to>`, `<Navigate to>` and `navigate()` target in `frontend/src` is a constant, a lookup in a fixed table (`HOME_FOR_ROLE`, `frontend/src/lib/session.jsx`), or `/menu?category=<slug>` with a server-supplied slug behind a fixed prefix (`frontend/src/site/MenuSection.jsx:70`). No navigation target is taken from the URL or user input, so no exploitable path was found. **Verified in code**; not tested by exploitation |
| react-router | 6.30.6 | GHSA-337j-9hxr-rhxg — constructor injection via `deserializeErrors()` in SSR hydration | `>=6.4.0 <7.18.0` | Moderate | Version matches. The app uses `BrowserRouter` with client-side rendering only (`frontend/src/main.jsx`); there is no server-side rendering, data router or hydration payload. The affected code path appears unused. **Verified in code** that SSR/hydration APIs are not called; whether the vulnerable function is otherwise reachable is **Not verified** |

`npm audit` reports the fix as `react-router-dom@7.18.4`, a major-version upgrade. Recorded as finding F-06.

## 3. Frontend — build-time tools (not shipped to browsers)

All of these are development dependencies in the lockfile. They run when the site is built, on source files
the project controls, and are not included in the built site.

| Package | Locked version | Advisory | Affected range (per advisory) | Severity (npm) |
|---|---|---|---|---|
| braces | 3.0.3 | GHSA-vfj7-8cjw-p6xm — stack exhaustion through deeply nested patterns | `<=3.0.3` | High |
| postcss-selector-parser | 6.1.4 | GHSA-rj75-hqrm-r3gf — quadratic complexity in selector parsing | `<7.1.6` | Moderate |

`npm audit` also flags `micromatch` 4.0.8, `chokidar` 3.6.0, `fast-glob` 3.3.3, `postcss-nested` 6.2.0 and
`tailwindcss` 3.4.19, but only because they depend on the two packages above; it returned no separate
advisory for them. Total reported: 9 entries (5 high, 4 moderate), all traced to the four advisories in this
document.

Both are denial-of-service issues triggered by crafted input to the build tools. The inputs here are the
project's own source files, so the practical risk is to a build machine processing malicious source, not to
visitors. `npm audit` reports the fix as `tailwindcss@4.3.3`, a major-version upgrade. Recorded as finding F-07.

Other build tools in the lockfile with no advisory returned: vite 6.4.4, @vitejs/plugin-react 4.7.0,
esbuild 0.25.12, rollup 4.64.4, postcss 8.5.29, autoprefixer 10.6.1, nanoid 3.3.20.

## 4. Backend — installed versions and advisory lookup

Runtime packages (declared in `requirements.txt`) as installed in `backend/.venv`:

| Package | Declared range | Installed |
|---|---|---|
| fastapi | `>=0.118,<1` | 0.143.0 |
| starlette (via fastapi) | — | 1.7.0 |
| uvicorn[standard] | `>=0.37,<1` | 0.54.0 |
| sqlalchemy | `>=2.0.44,<2.1` | 2.0.54 |
| alembic | `>=1.17,<2` | 1.20.0 |
| psycopg[binary] | `>=3.2.10,<4` | 3.3.6 |
| pydantic / pydantic-core | `>=2.12,<3` | 2.14.0 / 2.50.0 |
| pydantic-settings | `>=2.11,<3` | 2.15.0 |
| email-validator | `>=2.2,<3` | 2.3.0 |
| argon2-cffi / bindings | `>=25.1` | 25.1.0 / 26.1.0 |
| phonenumbers | `>=9.0` | 9.0.41 |
| tzdata | (any) | 2026.5 |

Notable transitive packages: anyio 4.15.1, h11 0.16.0, httptools 0.9.0, uvloop 0.23.0, websockets 17.2,
watchfiles 1.3.0, python-dotenv 1.2.4, PyYAML 6.0.3, Mako 1.4.3, MarkupSafe 3.0.4, dnspython 2.9.0,
idna 3.20, cffi 2.1.1, greenlet 3.5.6, click 8.5.0. Test-only: pytest 9.1.1, httpx 0.28.1, httpcore 1.0.9.

**OSV result:** all 45 installed packages were queried. **No advisory was returned for any runtime, transitive
or test package.**

One advisory match was returned, for the installer rather than the application:

| Package | Installed | Advisories returned | Notes |
|---|---|---|---|
| pip | 25.1.1 | GHSA-4xh5-x5gv-qwph (fixed 25.3), GHSA-6vgw-5pg2-w6jp (fixed 26.0), GHSA-58qw-9mgm-455v and GHSA-jp4c-xjxw-mgf9 (fixed 26.1), GHSA-wf93-45jw-7689 (fixed 26.1.2), GHSA-qwm4-qh6w-59xr (fixed 26.2.0) | `pip` is the package installer in the local development environment. These concern installing untrusted or malicious packages. It is not imported by the application. The `pip` version inside the production image comes from the `python:3.13-slim` base image and is **Not verified** |

Recorded as finding F-08.

## 5. Observations that are not vulnerabilities

- `argon2-cffi`, `phonenumbers` and `tzdata` have no upper bound in `requirements.txt`, so a future major
  release would be installed without review.
- `requirements.txt` installs `uvicorn[standard]`, which brings `watchfiles` and `websockets`. The
  application does not use WebSockets and production does not use reload; these add unused code to the image.
- The frontend loads fonts from Google's servers at run time (`frontend/index.html:9-11`). That is a
  third-party dependency delivered outside the lockfile and without Subresource Integrity.

## 6. Not verified

- Package versions inside any production container image.
- Vulnerabilities in base images' operating-system packages (no image scan was run).
- Licence compliance.
- Advisories published after 13 October 2026.

---

## Update — 13 October 2026 (remediation)

Sections 1–6 describe commit `834e59f26541e51977dcec21047423aa82f2c1a9` and are left as written. Since then,
in the commits that follow it on `release/wendy-production-review`:

- **Backend is now locked.** `backend/requirements.txt` (33 pins) and `requirements-dev.txt` (41 pins in
  total with test tools) carry exact versions and hashes; the image installs with `--require-hashes`. A clean
  build contained exactly the locked packages on Python 3.13.16 with pip 26.2.1. Notable versions: fastapi
  0.143.0, starlette 1.7.0, uvicorn 0.54.0, sqlalchemy 2.0.54, psycopg 3.3.6, pydantic 2.14.1, argon2-cffi
  25.1.0. `websockets`, `watchfiles` and `PyYAML` are no longer installed.
- **OSV lookup of all 41 pins: no advisories** (13 Oct 2026).
- **pip:** the build image has 26.2.1, outside the ranges of the six advisories listed in section 4.
- **`postcss-selector-parser`** raised to 7.1.6 by an `overrides` entry; GHSA-rj75-hqrm-r3gf no longer matches.
- **Still matching, no compatible fix available:**

| Package | Installed | Advisory | Why not updated | Applicability here |
|---|---|---|---|---|
| react-router / react-router-dom | 6.30.6 | GHSA-wrjc-x8rr-h8h6, GHSA-337j-9hxr-rhxg | 6.30.6 is the newest 6.x; fixes exist only in 7.18.0+, a major upgrade | Shipped to browsers. No navigation target comes from user input or the URL, and there is no server-side rendering, so no exploitable path was found. Not tested by exploitation |
| braces (via tailwindcss 3.4.19) | 3.0.3 | GHSA-vfj7-8cjw-p6xm | 3.0.3 is the latest release; no patched version exists | Build-time only, on the project's own files. Not shipped |

`npm audit` now reports 7 entries (5 high, 2 moderate), all of them the two rows above and packages that
depend on them.

### Remaining advisories in detail (looked up 13 October 2026)

Source: `npm audit` against `frontend/package-lock.json`, and the OSV record for each ID. Severity and
scores are the advisory's own, not an assessment of this site.

| | GHSA-wrjc-x8rr-h8h6 | GHSA-337j-9hxr-rhxg | GHSA-vfj7-8cjw-p6xm |
|---|---|---|---|
| CVE | CVE-2026-53669 | CVE-2026-53666 | CVE-2026-93687 |
| Package | `react-router` (pulled in by `react-router-dom`) | `react-router` | `braces` |
| Installed | 6.30.6 | 6.30.6 | 3.0.3 |
| Affected versions | >= 6.0.0, < 7.18.0 | >= 6.4.0, < 7.18.0 | <= 3.0.3 (every release) |
| First fixed version | 7.18.0 | 7.18.0 | None published |
| Advisory severity | Moderate (CWE-601, open redirect) | Moderate, CVSS 3.1 6.1 (CWE-470) | High, CVSS 3.1 7.5 (CWE-674, stack exhaustion) |
| What it is | A backslash in a `<Link>` / `useNavigate` target can send the browser to another site | Constructor injection in `deserializeErrors()` during server-side-rendering hydration | Deeply nested brace patterns crash the process |
| In the shipped site? | Yes | Yes (the code is in the bundle) | No. Build and dev tooling only |
| How it gets here | Direct dependency | Direct dependency | `tailwindcss` 3.4.19 -> `chokidar` 3.6.0 and `micromatch` 4.0.8 -> `braces` |

`npm audit` also lists `react-router-dom`, `chokidar`, `micromatch`, `fast-glob` and `tailwindcss`. Those five
entries have no advisory of their own; they are listed because they depend on the packages above.

**Applicability, and how far it was checked**

- **GHSA-wrjc-x8rr-h8h6.** Needs a navigation target an attacker can influence. Every `<Link to>`,
  `<Navigate to>` and `navigate()` call in `frontend/src` was read: targets are string constants or fixed
  lookups by role (`auth/AccountPages.jsx:52,62,77,146`, `staff/StaffApp.jsx:115,117`,
  `customer/CustomerApp.jsx:41`, `site/Header.jsx`, `auth/AuthLayout.jsx:46`). One target includes data:
  `site/MenuSection.jsx:70` builds `/menu?category=<slug>`, where the slug comes from the menu the owner
  manages and follows a fixed `/menu?` prefix, so it cannot change the destination site. There is no
  `?next=` or similar return-address parameter. **Assessment: not reachable in the current code.
  Verified by reading the code only; no exploit was attempted.** It becomes reachable if a later change
  navigates to a value taken from the URL or user input.
- **GHSA-337j-9hxr-rhxg.** Needs server-side rendering with hydration data. The site is client-rendered only:
  `frontend/src/main.jsx:19` uses `BrowserRouter`; there is no `hydrateRoot`, `renderToString`, static handler
  or data router anywhere in `frontend/src`. **Assessment: not reachable. Verified by reading the code only.**
- **GHSA-vfj7-8cjw-p6xm.** Needs a hostile glob pattern handed to the build tool. The only patterns are the
  two fixed ones in `frontend/tailwind.config.js:3`. Nothing from visitors reaches it, and it does not run on
  the production server at request time (the image serves pre-built files). **Assessment: not reachable by a
  site visitor. The worst case is a failed build on a machine building an untrusted branch.**

**Why they are not updated.** `react-router` needs a move from 6 to 7 (routing API changes; every page and
redirect would need re-testing). `braces` has no fixed release; removing it means moving to Tailwind 4, a
rewrite of the styling configuration. Both are "unrelated major upgrades" for this round and were left alone
on purpose. Neither was evaluated by trying the upgrade.

**What would change this.** A fixed 6.x release of `react-router`, or a patched `braces`, should be taken
immediately. Re-run `npm audit` before each release.
