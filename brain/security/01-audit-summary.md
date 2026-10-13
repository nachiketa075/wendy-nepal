# Security audit summary — Wendy Juice Shop

| | |
|---|---|
| **Audited commit** | `834e59f26541e51977dcec21047423aa82f2c1a9` |
| **Branch** | `release/wendy-production-review` (local and `origin` at the same commit; `main` is `c47cfc5` and was not audited) |
| **Audit date** | 13 October 2026 |
| **Working tree at audit** | Clean (no uncommitted changes) |
| **Auditor** | Claude (AI assistant), which also wrote most of this code. Treat this as a structured self-review, not an independent assessment |

## Scope

Source code, configuration and tests in the repository at the commit above: `backend/`, `frontend/`,
`docker-compose.yml`, `docker-compose.prod.yml`, `frontend/Caddyfile`, `scripts/`, dependency manifests and
the git history.

Out of scope, and therefore **not verified**: any deployed environment (none exists), the hosting provider,
DNS and certificates, real email delivery, the connected Vercel project's settings, the GitHub account's
settings, and the security of staff devices.

## Method

1. Read the code paths for authentication, sessions, authorisation, booking, staff and owner functions,
   rate limiting, configuration, email, logging and deployment files.
2. Ran the existing test suite against a throwaway PostgreSQL container (database name `wendy_audit_test`,
   in memory, removed afterwards): **152 passed**.
3. Ran one read-only probe on that throwaway database to confirm how database errors are worded (finding F-01).
4. Reviewed dependencies from `frontend/package-lock.json`, `backend/requirements.txt` and the installed
   packages; looked them up with `npm audit` and the OSV database.
5. Searched the git history for committed secrets, environment files, dumps and logs.

No development or production database was touched, no customer was contacted, no third-party system was
probed, and no destructive test was run.

## How to read the status labels

- **Verified in code** — the control was read in the source at the cited lines.
- **Verified by an executed test** — an automated test exercising it was run in this audit and passed.
- **Not verified** — it could not be confirmed from this repository (usually because it depends on a
  deployment that does not exist).

A passing test shows the behaviour for the cases the test covers. It is not proof that the control cannot be
bypassed. Absence of documentation was not counted as absence of a control.

## Overall result

No critical or high-severity defect was found in the application code at this commit. Authentication,
session handling, role and permission checks and booking-ownership checks are implemented server-side and
are covered by tests.

Eighteen findings are recorded in `04-findings-and-recommendations.md`. The ones to resolve before real
customers use the site:

| ID | Severity | Finding |
|---|---|---|
| F-01 | Medium | Database errors are logged with the row values they contain (names, emails, phone numbers) |
| F-02 | Medium | Backend has no lockfile; production images resolve dependency versions at build time |
| F-03 | Medium | Backups are unencrypted local files with no off-server copy (operational, not yet set up) |
| F-04 | Low–Medium | No Content-Security-Policy header |
| F-05 | Low–Medium | Owner and staff accounts have no second factor |
| F-06 | Low | `react-router` 6.30.6 matches two published advisories; reachability in this app appears limited |

Counts by severity: Critical 0, High 0, Medium 3, Low–Medium 2, Low 9, Informational 4.

## What this audit does not establish

- That the application is secure. It establishes what was checked and what was found.
- Anything about a live deployment: TLS configuration, firewalling, backup storage, monitoring and secret
  handling on a server are all **Not verified**.
- That the production container images contain the dependency versions examined here (see F-02).
- Resistance to load, denial of service, or a skilled manual penetration test. None was performed.

## Later work

Remediation carried out after this audit (13 October 2026, committed after the audited commit on the same branch) is recorded in
the "Status update" section at the end of `04-findings-and-recommendations.md`. This summary still describes
the audited commit.

## Documents

| File | Contents |
|---|---|
| `01-audit-summary.md` | This summary |
| `02-controls-verification.md` | Each security control with its status and evidence |
| `03-dependency-review.md` | Lockfiles, installed versions and advisory matches |
| `04-findings-and-recommendations.md` | Findings with locations, impact and recommended fixes; status update |
| `threat-model.md` | Assets, actors, threats and their treatment |
| `attack-surface.md` | Every reachable endpoint and interface |
| `secrets.md` | Inventory of secrets and how they are handled (no values) |
| `security-checklist.md` | Controls done, open, pending deployment, and owner decisions |
| `mfa-plan.md` | Proposed second-factor sign-in for owner and staff (not implemented) |
