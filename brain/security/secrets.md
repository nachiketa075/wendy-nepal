# Secrets inventory and handling

**Baseline:** commit `834e59f26541e51977dcec21047423aa82f2c1a9` (the audited commit) on `release/wendy-production-review`, plus the remediation changes of 13 October 2026 described in `04-findings-and-recommendations.md` ("Status update"), committed after it on the same branch (`git log 834e59f..release/wendy-production-review`).

This document lists what must be kept secret, where it lives and how to rotate it. **It contains no secret
values, and none were read or printed while writing it.**

## 1. Inventory

| Secret | Used by | Where it lives | In the repository? | Rotation |
|---|---|---|---|---|
| Database password (`POSTGRES_PASSWORD`) | PostgreSQL container, API connection string | `.env.production` on the server (mode 600) | No. `.env.production.example` has an empty value | Set a new value, `ALTER USER` in the database, restart API. Brief downtime |
| SMTP password (`SMTP_PASSWORD`) | `backend/app/email_delivery.py:66-67` | `.env.production` | No (empty in the template) | Issue a new credential at the provider, update the file, restart API |
| Session tokens | Browser cookie; `account_sessions.token_hash` | Cookie in each browser; **only a SHA-256 digest** in the database (`security.py:41-53`) | No | Expire after `SESSION_TTL_HOURS`; revoked on password change, reset, deactivation. To end all sessions: empty the `account_sessions` table |
| CSRF tokens | `account_sessions.csrf_token` | Database (plain) and in page memory | No | Per session |
| Account passwords | Sign-in | **Argon2id hashes** in `accounts.password_hash` (`security.py:26`) | No | By the user, by reset link, or `python -m app.cli set-password` |
| Reset and staff setup tokens | `routers/auth.py:77-93` | The emailed or hand-passed link; **only a digest** in `password_reset_tokens` | No | Single-use; reset 30 minutes, setup 72 hours (`config.py`) |
| Backup **private** key | Decrypting backups | **Off the server**: owner's/developer's computer plus a second safe copy | No | See "Backup key" below |
| Backup public key | `scripts/backup.sh:53` | Server, path in `.env.backup` | No. Not a secret | Replaced together with the private key |
| Off-server storage credentials | `rclone` | rclone's own config file on the server (mode 600) | No | At the storage provider; update the rclone config |
| TLS private key | Caddy | `caddy-data` Docker volume | No | Automatic renewal by Caddy |
| GitHub access token | Pushing code | The developer's machine or credential manager | No | At GitHub; use a fine-grained token limited to this repository |
| Server SSH key | Operator access | The operator's machine | No | Replace the authorised key on the server |

There is **no application signing secret**: sessions are random tokens looked up in the database, not signed cookies or JWTs.

## 2. What was checked in the repository

| Check | Result |
|---|---|
| `.env`, `.env.production`, `.env.backup` ignored by git | **Verified** (`.gitignore`; `git check-ignore`) |
| Only templates committed | **Verified**: `.env.example`, `.env.production.example`, and `.env.backup.example`. Secret values in them are empty |
| Git history free of tokens, private keys, filled-in passwords | **Verified** by pattern search over all history (0 matches) on 13 Oct 2026. A pattern search cannot prove absence of every possible secret |
| No dumps, logs or development mailbox files committed | **Verified** (history search, 0 matches); `backups/`, `*.dump`, `*.sql`, `backend/dev-mailbox/` are ignored |
| No default or hard-coded credentials in code | **Verified**: passwords appear only in `backend/tests/` as test fixtures for accounts created inside the throwaway test database |
| Secrets absent from logs | **Verified** for application logging paths (see `tests/test_logging.py` and F-01). The database password is part of `DATABASE_URL`; it is not logged by the application. **Not verified** for a real host's process listings or orchestration logs |
| Docker images free of secrets | **Verified in code**: `backend/.dockerignore` excludes `.env`; secrets are passed as environment at run time, not build arguments |

## 3. Handling rules

1. Secrets go only in `.env.production` (and rclone's config) on the server, readable by the deploy user only.
2. Never paste a secret into chat, an issue, a commit message or a screenshot.
3. Use different values in development and production. The development `.env` is for local use only.
4. `OWNER_PASSWORD` as an environment variable (`backend/app/cli.py:35`) is for scripted setup only. Prefer
   the interactive prompt; if the variable is used, it can remain in shell history.
5. Staff setup links are secrets until used. Send them privately; they expire and work once.
6. Environment variables are visible to anyone who can run `docker inspect` on the server. Server access is
   therefore equivalent to holding the database and SMTP passwords.

## 4. Backup key

- Generated on a trusted computer, **never on the server**. Only the public half is copied to the server.
- Two copies of the private key in separate safe places; record who holds them. Losing it makes every
  backup unreadable; there is no recovery.
- If it may have been exposed: generate a new pair, replace the public key on the server, take a fresh
  backup, and delete or re-encrypt older backups.
- Full procedure: `docs/OPERATIONS.md`, "Backups" and "Key recovery".

## 5. If a secret leaks

| Leaked | Do |
|---|---|
| Database password | Rotate it; check the database is not reachable from outside the server; review access |
| SMTP password | Revoke at the provider; rotate; check the provider's sent log |
| A session cookie or suspected account takeover | Change that account's password (ends its sessions); for staff, the owner uses "Sign out everywhere" or deactivates the account |
| GitHub token | Revoke it at GitHub immediately; review recent pushes |
| Backup private key | Rotate as in section 4 |
| `.env.production` as a whole | Rotate everything in it; assume the database contents were readable |

## 6. Not verified

File permissions, process visibility and secret storage on a real server; the storage provider's access
controls; who actually holds copies of the backup private key. None of these exist yet.
