# Controls verification

**Audited commit:** `834e59f26541e51977dcec21047423aa82f2c1a9` (branch `release/wendy-production-review`), 13 October 2026.

Status values: **Code** = Verified in code. **Test** = Verified by an executed test (run in this audit on a
throwaway database; 152 passed). **Not verified** = could not be confirmed from the repository.

Where both apply, both are listed. A passing test covers only the cases it exercises. Test names refer to
files under `backend/tests/`.

## 1. Authentication

| Control | Status | Evidence |
|---|---|---|
| Passwords hashed with Argon2id; plaintext never stored | Code, Test | `backend/app/security.py:26` `hash_password`, `:30` `verify_password`. `test_accounts.py::test_registration_creates_a_customer_and_signs_them_in` |
| Unknown email and wrong password cost the same and answer the same | Code, Test | Dummy hash at `security.py:23`, used at `:32`. `test_accounts.py::test_wrong_password_and_unknown_email_get_the_same_answer` |
| Minimum password length 12 enforced server-side | Code, Test | `schemas.py:425` `Password`; `security.py:18`; `cli.py:33`. `test_accounts.py::test_registration_validation` |
| Password strength beyond length (breached-password check, complexity) | Not verified | No such check exists in code. See F-13 |
| Second factor for owner/staff | Not verified | Not implemented. See F-05 |
| Public registration can only create a customer | Code, Test | `routers/auth.py:109` sets `role="customer"`; `schemas.py:455` `RegisterIn` has no role field and `:21` forbids extra fields. `test_accounts.py::test_registration_rejects_privileged_fields` |
| No public owner or employee registration | Code, Test | Owner creation only in `cli.py:72`; employee creation only in `routers/owner.py:59` behind `require_owner` (`:22`). `test_accounts.py::test_there_is_no_public_owner_or_employee_registration` |
| Sign-in page (`portal`) cannot raise a role | Code, Test | `routers/auth.py:136-138`; role read from the account at `:49-58`. `test_accounts.py::test_the_sign_in_page_never_decides_the_role` |
| Invited employee has no usable password until they set one | Code, Test | `routers/owner.py:71` `password_hash=None`; `security.py:32` returns false for a missing hash. `test_employees.py::test_owner_invites_an_employee_who_sets_their_own_password` |
| No default or seeded accounts | Code | Migrations `backend/alembic/versions/0001`–`0003` insert no account rows other than copying existing `owners` (`0003_accounts_roles_booking_workflow.py:45-48`). Test fixtures are confined to `backend/tests/` |

## 2. Sessions and cookies

| Control | Status | Evidence |
|---|---|---|
| Random 256-bit session token; only a SHA-256 digest stored | Code, Test | `security.py:41-53` `create_session`, `:37` `digest`. `test_accounts.py::test_login_sets_a_hardened_cookie_and_stores_only_a_digest` |
| Cookie is `HttpOnly`, `SameSite=Strict`, path `/api` | Code, Test | `routers/auth.py:64-72`. Same test as above |
| Cookie is `Secure` in production | Code, Test | `config.py:71-74` `secure_cookies`; production refuses `COOKIE_SECURE=false` at `config.py:54`. `test_accounts.py::test_secure_cookie_in_production` |
| `Secure` flag actually set on a deployed site | Not verified | No deployment exists. (Observed once on a local throwaway production stack on 12 Oct 2026, before this audit; not re-run here) |
| Session expiry enforced on every request | Code, Test | `security.py:70`. `test_accounts.py::test_logout_expiry_and_forged_cookies` |
| Logout deletes the server-side session | Code, Test | `routers/auth.py:148-152`. Same test |
| Password change signs out other sessions; reset signs out all | Code, Test | `routers/auth.py:177`, `:221`. `test_accounts.py::test_password_change_needs_the_current_password_and_signs_out_other_devices`, `::test_reset_token_is_single_use_short_lived_and_signs_everyone_out` |
| Deactivated account is rejected on its next request | Code, Test | `security.py:70` checks `is_active` each request; `routers/owner.py:108-111`. `test_employees.py::test_deactivation_takes_effect_immediately` |
| Owner can revoke an employee's sessions | Code, Test | `routers/owner.py:117-123`. `test_employees.py::test_owner_can_revoke_sessions_and_issue_a_new_link` |
| Idle timeout / sliding expiry | Not verified | Not implemented; sessions have a fixed lifetime (`config.py:19`). See F-14 |
| Session tokens absent from browser storage | Code | Only a sound preference uses `localStorage` (`frontend/src/staff/StaffApp.jsx:17`, `:100`); no token handling in `frontend/src/lib/api.js` or `session.jsx` beyond the in-memory CSRF value |

## 3. CSRF and cross-origin

| Control | Status | Evidence |
|---|---|---|
| CSRF token required for every state-changing authenticated request | Code, Test | `security.py:75-84` `require_session` (constant-time compare at `:82`). `test_accounts.py::test_csrf_token_and_origin_are_required_for_changes` |
| Requests with a foreign `Origin` refused | Code, Test | `main.py:41-52` `reject_cross_site_writes`. Same test |
| Production CORS restricted to explicit HTTPS origins; wildcard refused | Code, Test | `config.py:49-53`; `main.py:62-69`. `test_accounts.py::test_secure_cookie_in_production` |
| Login and registration protected against cross-site submission | Code | No session exists yet, so no CSRF token applies; protection is the `Origin` check (`main.py:46`) plus `SameSite=Strict`. A request with no `Origin` header is accepted (see F-15) |

## 4. Authorisation

| Control | Status | Evidence |
|---|---|---|
| Role read from the database account on every request | Code | `security.py:87-88` `require_account`, `:95-106` `require_role` |
| All `/api/staff/*` routes require owner or employee | Code, Test | Router dependency `routers/staff.py:42`. `test_staff.py::test_staff_and_owner_routes_reject_anonymous_and_customers` (every route, enumerated from the router) |
| All `/api/owner/*` routes require owner; employees with every permission are refused | Code, Test | `routers/owner.py:22`. `test_staff.py::test_owner_routes_reject_employees_even_with_every_permission` |
| Route inventory matches what the access tests enumerate | Test | `test_staff.py::test_route_inventory_is_as_expected` (17 staff, 7 owner) |
| Per-action employee permissions | Code, Test | `permissions.py` `TRANSITION_PERMISSION`; `booking_service.py:263`; `routers/staff.py:124`, `:144`, `:158`, `:206`. `test_staff.py::test_each_action_needs_its_own_permission` (six actions) |
| Employees default to no permissions | Code, Test | `schemas.py:515`; `routers/owner.py:72`. `test_staff.py::test_employee_without_permissions_can_do_nothing` |
| Permission changes apply on the next request | Code, Test | `models.py:52-57` `Account.can` reads the live row. `test_employees.py::test_permission_changes_apply_on_the_next_request_without_signing_in_again` |
| Employees cannot grant permissions, create accounts or edit their own | Code, Test | Owner-only router; `schemas.py:485` `ProfileUpdate` has no permission field. `test_employees.py::test_employees_cannot_manage_employees_or_their_own_privileges` |
| Owner endpoints act only on employee accounts | Code, Test | `routers/owner.py:35-39` `_get_employee`. `test_employees.py::test_owner_endpoints_only_manage_employee_accounts` |
| Booking scope: `view_assigned` sees only own assignments; out of scope is 404 | Code, Test | `routers/staff.py:48-54` `_scope`; `booking_service.py:202-217`. `test_staff.py::test_view_assigned_limits_the_scope` |
| Contact fields removed from the response without `bookings.view_contact` | Code, Test | `booking_service.py:398`, `:418-419`. `test_staff.py::test_contact_details_are_left_out_of_every_response_without_permission` (list, detail, notes and status responses) |
| Free-text fields cannot leak contact details to restricted staff | Not verified | `special_requests` and `internal_notes` are returned to anyone who can view the booking (`booking_service.py:423`, `:425`). See F-10 |
| Only the owner can confirm booking rules for real use | Code, Test | `routers/staff.py:187-188`. `test_staff.py::test_settings_permission_and_owner_only_confirmation` |
| Customer sees only their own bookings | Code, Test | Every query filters on `customer_id` (`routers/customer.py:43`, `:63`; `booking_service.py:339`). `test_customer.py::test_customer_sees_only_their_own_bookings` |
| Customer cannot set customer, status, reference, assignment or notes | Code, Test | `schemas.py:27` `BookingCreate` (extra fields forbidden); `booking_service.py:142-175`. `test_customer.py::test_customer_booking_is_pending_linked_and_uses_server_values` |
| Guest bookings never auto-linked by phone or email | Code, Test | `booking_service.py:148`, `:162` (link only from the session). `test_customer.py::test_guest_bookings_are_never_claimed_by_matching_contact_details` |
| Internal notes, history and audit data never returned to customers | Code, Test | `schemas.py:73` `CustomerBookingOut`; `booking_service.py:377-392`. `test_customer.py::test_customer_response_has_no_internal_fields` |
| No public lookup of a booking by reference | Code, Test | No such route in `routers/public.py`. `test_bookings.py::test_no_public_endpoint_lists_or_reads_bookings` |

## 5. Booking integrity

| Control | Status | Evidence |
|---|---|---|
| New requests always `pending`; never auto-confirmed | Code, Test | `booking_service.py:171`. `test_bookings.py::test_valid_request_is_persisted_as_pending` |
| Idempotency; same key with different data is a conflict | Code, Test | `booking_service.py:112-139`. `test_bookings.py::test_reusing_an_idempotency_key_with_different_details_is_a_conflict`, `::test_rapid_concurrent_clicks_create_one_booking` |
| Explicit status transitions with time rules | Code, Test | `permissions.py` `ALLOWED_TRANSITIONS`; `booking_service.py:230-286`. `test_staff.py::test_full_status_flow_with_time_rules`, `::test_no_show_only_after_the_time_and_past_requests_cannot_be_confirmed` |
| Concurrent staff changes cannot silently overwrite | Code, Test | Row lock `booking_service.py:213`; version check `:220-227`. `test_staff.py::test_simultaneous_staff_actions_cannot_both_win`, `::test_stale_version_is_a_conflict_not_an_overwrite` |
| Cancellation request does not cancel by itself | Code, Test | `booking_service.py:336-361`. `test_customer.py::test_cancellation_request_does_not_cancel_by_itself` |
| Production refuses bookings until the owner confirms rules | Code, Test | `booking_service.py:47-53`. `test_bookings.py::test_production_requires_owner_confirmed_settings` |
| Business time is Asia/Kathmandu | Code, Test | `config.py:27`; `booking_service.py:36`. `test_bookings.py::test_past_time_today_is_judged_in_kathmandu_time` |
| No table capacity or live availability is claimed | Code | No capacity model exists; `booking_service.py:1-5` |

## 6. Password reset and employee setup tokens

| Control | Status | Evidence |
|---|---|---|
| 256-bit random token, stored only as a hash | Code, Test | `routers/auth.py:84-86`. `test_accounts.py::test_reset_request_answers_the_same_for_known_and_unknown_emails` |
| Expiring and single-use; earlier tokens cancelled | Code, Test | `routers/auth.py:79-83`, `:216-219`. `test_accounts.py::test_reset_token_is_single_use_short_lived_and_signs_everyone_out`, `::test_expired_reset_token_is_refused`, `::test_a_new_reset_request_cancels_the_previous_link` |
| Same response whether or not the email exists | Code, Test | `routers/auth.py:182-207`. `test_accounts.py::test_reset_request_answers_the_same_for_known_and_unknown_emails` |
| Response time does not depend on whether the email exists | Code | Email is queued after the response (`routers/auth.py:199`). The remaining difference (one token insert) was not measured: **timing equality is Not verified** |
| Token kept out of server logs | Code, Test | Token is in the URL fragment (`routers/auth.py:90-93`); frontend reads and clears it (`frontend/src/auth/AccountPages.jsx`, `ResetPage`). `test_accounts.py::test_reset_link_keeps_the_token_out_of_server_logs` checks the link shape only |
| Token absent from a real proxy's access log | Not verified | Depends on deployment. (Observed on the local throwaway stack on 12 Oct 2026; not re-run here) |
| No delivery is claimed when email is not configured | Code, Test | `routers/auth.py:188-190`. `test_accounts.py::test_without_email_delivery_nothing_is_claimed_or_created` |
| Development email file mode cannot run in production | Code, Test | `config.py:56-57`. `test_accounts.py::test_secure_cookie_in_production` |
| Development email file mode keeps links out of the log | Code, Test | `email_delivery.py:41-50`. `test_accounts.py::test_dev_file_delivery_writes_to_a_folder_not_the_log` |
| Real SMTP delivery works and is authenticated over TLS | Not verified | `email_delivery.py:57-68` was read; never run against a mail server |

## 7. Abuse protection

| Control | Status | Evidence |
|---|---|---|
| Rate limits stored in PostgreSQL, shared across workers | Code, Test | `rate_limit.py:20-46`. `test_bookings.py::test_rate_limit_is_shared_through_the_database` (storage only; not run with multiple worker processes) |
| Limits behave correctly with two or more API workers | Not verified | The advisory lock at `rate_limit.py:26` is designed for it; no multi-process test exists |
| Limiter keys stored as digests, not addresses or emails | Code, Test | `rate_limit.py:22`. Same test |
| Sign-in limited per email+address, per address and per email | Code, Test | `routers/auth.py:125-130`. `test_accounts.py::test_login_is_rate_limited`, `::test_one_stranger_cannot_lock_an_account_for_everyone` |
| Registration, reset, reset-confirm, password change, booking and cancellation limited | Code | `routers/auth.py:104`, `:172`, `:186-187`, `:212`; `routers/public.py:89-90`; `routers/customer.py:26`, `:73`. Only booking and sign-in limits have tests (`test_bookings.py::test_booking_endpoint_is_rate_limited`) |
| Visitor address derived correctly behind the proxy | Not verified | `rate_limit.py:65-70` takes the last `X-Forwarded-For` entry when `TRUST_PROXY_HEADERS` is true (`docker-compose.prod.yml:21`). Correct for exactly one trusted proxy; depends on the real topology. See F-11 |
| Request body size capped | Code | `frontend/Caddyfile:17-19` (256 KB). Field lengths capped in `schemas.py` |
| Automated-submission (bot) protection on public forms | Not verified | None beyond rate limits. See F-09 |

## 8. Input handling and injection

| Control | Status | Evidence |
|---|---|---|
| Unknown request fields rejected | Code, Test | `schemas.py:19-21` `StrictModel`. `test_bookings.py::test_customer_cannot_supply_server_controlled_fields` |
| Parameterised SQL only | Code | ORM queries throughout; raw SQL in `rate_limit.py:26-38`, `:57` and `routers/public.py:34` uses bound parameters or constants. No string-built SQL found in `backend/app/` |
| Phone and email validated server-side | Code, Test | `schemas.py` `_normalise_phone`, `EmailStr`. `test_bookings.py::test_invalid_requests_are_rejected_and_not_saved` |
| Output encoded in the browser | Code | No `dangerouslySetInnerHTML`, `innerHTML`, `eval` or `document.write` in `frontend/src` (searched). React escapes text by default |
| External links opened with `rel="noopener noreferrer"` | Code | All `target="_blank"` uses in `frontend/src` carry it (the one multi-line case is `staff/BookingsPanel.jsx:236-237`) |
| Content-Security-Policy | Not verified | No CSP header is configured. See F-04 |

## 9. Error handling, logging and caching

| Control | Status | Evidence |
|---|---|---|
| Clients never receive stack traces | Code | `main.py:31-38`; consistent error shape in `errors.py` |
| API documentation disabled in production | Code | `main.py:21`, `:23` |
| Contact details, passwords and tokens kept out of application log calls | Code | Explicit log calls log only references and statuses (`booking_service.py:193`, `:285`; `email_delivery.py:49`, `:71`) |
| Logs free of personal data in all cases | **Not verified — contradicted** | Unhandled database errors are logged with their bound values. See F-01 |
| API responses not cached by browsers or proxies | Code, Test | `main.py:53-59`. `test_accounts.py::test_readiness_and_cache_headers` |
| Activity log of staff and owner actions | Code, Test | `activity.py`; `routers/owner.py:126-133`. `test_employees.py::test_activity_log_records_staff_and_owner_actions` |
| Sign-in successes and failures recorded for review | Not verified | Not implemented. See F-12 |
| Readiness check reveals no connection details | Code, Test | `routers/public.py:29-41`. `test_accounts.py::test_readiness_and_cache_headers` |

## 10. Configuration, secrets and deployment

| Control | Status | Evidence |
|---|---|---|
| Secrets only from environment; none committed | Code | `.gitignore` excludes `.env` and `.env.*` except the two templates. History search for tokens, private keys and filled-in passwords: 0 matches; only `.env.example` and `.env.production.example` were ever committed, both with empty secret values |
| Production refuses unsafe configuration | Code, Test | `config.py:47-64`. `test_accounts.py::test_secure_cookie_in_production` |
| Only the reverse proxy publishes ports in production | Code | `docker-compose.prod.yml:83-85` is the only `ports:` entry; `db` and `backend` have none |
| Development stack binds to localhost only | Code | `docker-compose.yml:42`, `:55`. Running `npm run dev` directly binds all interfaces (`frontend/vite.config.js:11`). See F-16 |
| API container runs as non-root, without reload | Code | `backend/Dockerfile:13-14`, `:20` |
| Migrations are an explicit release step | Code | `docker-compose.prod.yml:66-74`; `backend/Dockerfile:16-20` |
| HTTPS, HSTS and security headers at the proxy | Code | `frontend/Caddyfile:7-14`. Effective behaviour on a real domain: **Not verified** |
| Database reachable only on a private network | Code | Compose network only (`docker-compose.prod.yml`). On a real host: **Not verified** |
| Database connection encrypted in transit | Not verified | Not configured; acceptable on a single-host private network, required if the database moves to another host (F-17) |
| Backups encrypted and stored off the server | Not verified | `scripts/backup.sh` writes a private local file only. See F-03 |
| Container images reproducible and pinned | Not verified | Tags, not digests; backend versions unpinned. See F-02, F-18 |
| Monitoring and alerting | Not verified | Documented as guidance in `docs/OPERATIONS.md`; nothing configured |

## 11. Privacy

| Control | Status | Evidence |
|---|---|---|
| Booking form states why contact details are collected | Code | `frontend/src/site/Booking.jsx` (privacy paragraph); registration page `frontend/src/auth/AccountPages.jsx` `RegisterPage` |
| Data retention / deletion | Not verified | No automatic deletion exists; a proposal awaiting the owner's approval is in `docs/OPERATIONS.md` |
| Consent for identifiable people in published photos | Not verified | Eleven of the thirteen photos under `frontend/public/images/` show identifiable guests; consent is an open owner item (`docs/OWNER_CONFIRMATION.md`) |
| Third-party requests from visitors' browsers | Code | Fonts load from Google (`frontend/index.html:9-11`), which discloses visitor IP addresses to Google |
