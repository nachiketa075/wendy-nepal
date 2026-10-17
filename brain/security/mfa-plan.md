# Plan: second-factor sign-in for owner and staff (finding F-05)

**Baseline:** commit `834e59f26541e51977dcec21047423aa82f2c1a9` on `release/wendy-production-review`, plus the
remediation changes of 13 October 2026. **This is a proposal. Nothing in it is implemented**, and
no authentication code was changed in this round.

## Why

The owner account can read every customer's contact details, manage staff and change the menu and booking
rules. Today it is protected by a password, rate limits and, if email is configured, an emailed reset link.
A phished or reused password is enough to take it over.

## What exists today (read from the code)

- One `accounts` table for all roles; role is never taken from the client (`backend/app/models.py`, `Account`).
- `POST /api/auth/login` checks the password and immediately creates a full session
  (`backend/app/routers/auth.py:121-139`, `_start_session` at `:61`).
- Sessions are rows in `account_sessions`, looked up by token digest on every request
  (`backend/app/security.py:63-84`). Anything stored on the session row is therefore available per request.
- Password reset and staff setup share single-use hashed tokens (`routers/auth.py:77-93`, `:210-223`).
- Owners are created and can have passwords set from the server CLI (`backend/app/cli.py`).
- The owner can deactivate staff and revoke their sessions (`backend/app/routers/owner.py:95-123`).

## Recommended design

**Method: time-based one-time codes (TOTP, RFC 6238)** from an authenticator app (Google Authenticator,
Aegis, 1Password and so on). Free, works offline on a phone in Pokhara, needs no SMS provider. SMS codes are
not recommended: they cost money per message, need a provider, and are the weakest option. Passkeys
(WebAuthn) are stronger and could be added later as an alternative; they are more work to build and support.

**Who:** required for the owner. For employees, required when they hold any of `bookings.view_contact`,
`bookings.view_all`, `menu.manage` or `booking_settings.manage`; optional otherwise. The owner can require it
for everyone. Customers are out of scope.

### Data model (one additive migration)

| Table / column | Purpose |
|---|---|
| `account_mfa` (`account_id` unique, `secret_encrypted`, `confirmed_at`, `last_used_step`) | The TOTP secret, encrypted at rest; `last_used_step` blocks reuse of a code |
| `account_recovery_codes` (`account_id`, `code_hash`, `used_at`) | Ten single-use recovery codes, stored as Argon2 hashes |
| `account_sessions.mfa_verified_at` (nullable) | Marks a session that has passed the second step |
| `accounts.mfa_required` (boolean) | Set by the owner per employee; always true for owners once enrolled |

The TOTP secret must be recoverable to verify codes, so it cannot be hashed. Encrypt it with a key from a new
environment variable (`MFA_ENCRYPTION_KEY`), so a database dump or backup alone does not reveal it. That key
becomes a new secret to store and back up separately (add it to `secrets.md`).

### Sign-in flow

1. `POST /api/auth/login` verifies the password as now.
2. If the account has confirmed MFA, the session is created with `mfa_verified_at = NULL` and the response
   says `mfa_required: true`. A **pending** session may call only `POST /api/auth/mfa/verify` and logout.
3. `POST /api/auth/mfa/verify` takes a 6-digit code or a recovery code. On success it sets
   `mfa_verified_at`. Allow one time-step of clock drift; reject a step already used.
4. `require_session` (`security.py:75`) gains one check: if the account has MFA and the session is not
   verified, answer 401 with code `mfa_required`. Because every protected route already depends on it, no
   route needs individual changes. This is the single enforcement point, and it is server-side.
5. Limits: 5 code attempts per session, then the pending session is deleted; plus a per-account limit
   through the existing limiter (`rate_limit.py`).

### Enrollment

1. Signed-in user opens "My account" → "Set up two-step sign-in".
2. `POST /api/auth/mfa/enroll` (requires the current password again) creates an unconfirmed secret and
   returns the `otpauth://` URI. The page shows it as a QR code generated in the browser, plus the text secret.
3. `POST /api/auth/mfa/confirm` with a valid code sets `confirmed_at` and returns ten recovery codes,
   **shown once**, with a prompt to save or print them.
4. All other sessions for the account are revoked.
5. Owner: prompted at next sign-in after release, with a short grace period, then mandatory. An employee whose
   account is marked `mfa_required` is taken to enrollment at next sign-in and can do nothing else until done.

### Recovery and reset

| Situation | Path |
|---|---|
| Phone unavailable, has recovery codes | Enter a recovery code at the second step (single-use). Prompt to re-enroll |
| Employee lost phone and codes | Owner uses a new "Reset two-step sign-in" action on the Team tab. It clears the employee's MFA, revokes their sessions and records it in the activity log. The employee re-enrolls at next sign-in. The owner must confirm the request in person or by a known phone number |
| Owner lost phone and codes | Server command `python -m app.cli reset-mfa <email>`, which needs shell access to the server, the same trust level that can already create an owner. It clears MFA, revokes sessions and logs the action |
| Password forgotten | The existing reset link changes the password only. **It must not disable MFA**; otherwise the email account becomes a way around the second factor |
| Recovery codes used up or exposed | "Generate new recovery codes" (requires password and a current code); old codes stop working |
| Disabling MFA | Requires password and a current code. Not available to accounts where it is required |

### What must not happen

- No "remember this device for 30 days" in the first version: it weakens the control and adds cookie handling.
- The second step must not reveal whether the password was right for accounts without MFA (keep the current
  uniform failure answer at step 1).
- Codes, secrets and recovery codes never in logs or the activity log; only the events.

### Frontend

- A code-entry step after the sign-in form on `/owner/login` and `/employee/login`
  (`frontend/src/auth/AccountPages.jsx`, `LoginPage`), keeping the existing layout.
- Enrollment and recovery-code screens under the "My account" tab (`frontend/src/staff/StaffApp.jsx`).
- A QR code rendered locally. That needs one small, reviewed dependency or a hand-written encoder; either
  must be checked against the Content Security Policy (inline SVG or canvas, no external request).
- "Reset two-step sign-in" and a "required" toggle per employee on the Team tab.

### Tests to write (all on the throwaway test database)

- Session with MFA pending is refused on every staff, owner and customer route; only verify and logout work.
- Correct code verifies; wrong, expired and replayed codes do not; attempts are limited.
- Recovery code works once.
- Password reset does not remove MFA.
- Owner reset of an employee's MFA revokes sessions and is logged; an employee cannot reset anyone's.
- CLI reset works for an owner.
- Deactivation and permission changes still apply immediately.
- Accounts without MFA sign in exactly as today.

### Dependencies

`pyotp` (small, pure Python) for TOTP, and `cryptography` for encrypting the secret, both added through the
lockfile with hashes. Alternatively TOTP can be implemented with the standard library (`hmac`, `hashlib`,
`struct`) in about thirty lines, avoiding one dependency; the encryption still needs `cryptography`.

### Rollout

1. Build behind a setting that is off; run the tests.
2. Enable for the owner on a test deployment; rehearse loss-of-phone recovery by both paths.
3. Turn on for the real owner, then staff with sensitive permissions.
4. Update `secrets.md` (new key), `OPERATIONS.md` (reset procedure) and the staff onboarding steps.

### Effort and risk

Roughly two to three days of focused work including tests and the recovery paths. The main risk is locking
the owner out; the CLI reset and printed recovery codes address it, and it must be rehearsed before use.

### Until this is built

- The owner uses a long, unique password from a password manager.
- The owner's email account (the reset path, once email is configured) has its own second factor.
- Staff accounts get the fewest permissions that let them work; `bookings.view_contact` is given sparingly.
- Deactivate accounts the day someone leaves.

## Decisions needed from the owner

1. Is two-step sign-in required for all staff, or only those with sensitive permissions?
2. Who, besides the developer, may have server access to perform an owner MFA reset?
3. When should it be built: before launch, or in the first weeks after?
