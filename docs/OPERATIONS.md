# Operations: backups, recovery, monitoring, logs, retention

`dc` means `docker compose -f docker-compose.prod.yml --env-file .env.production`.

## Backups

```bash
scripts/backup.sh          # writes backups/wendy-<UTC time>.dump (compressed pg_dump, private permissions)
```

- **Schedule it daily** with cron on the server, for example `15 21 * * * cd /srv/wendy-nepal && scripts/backup.sh`
  (03:00 Pokhara time), and before every release.
- **Copy backups off the server** (object storage or another machine). A backup that lives only on the same
  disk does not protect against losing the server. This step is not set up; it needs the hosting decision.
- A backup contains customer names, phone numbers, emails and password hashes. Keep it private and encrypted
  at rest where it is stored. `backups/` is git-ignored.
- How many to keep is part of the retention decision below. A common starting point is 14 daily and 8 weekly.

## Restore rehearsal (safe, do it regularly)

```bash
scripts/restore-rehearsal.sh backups/wendy-<time>.dump
```

Restores the file into a throwaway PostgreSQL container, prints row counts and removes it. It never touches
the real database. This was run successfully on 12 Oct 2026 against a backup of the rehearsal stack.

## Restoring for real

Only when the production database is lost or corrupted. **This replaces current data with the backup.**

```bash
dc stop backend web                                  # stop writes
scripts/backup.sh                                    # if the database still answers, keep what is there
dc exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < backups/wendy-<time>.dump
dc run --rm migrate                                  # bring an older backup up to the current schema
dc up -d
curl -fsS https://YOUR-DOMAIN/api/ready
```

Anything recorded after the backup was taken is lost; tell the owner which period that is so bookings made
in it can be re-entered from phone or message records.

## Rolling back the application

If a new version misbehaves and **no migration ran** in that release:

```bash
git checkout <previous commit or tag>
dc build && dc up -d
```

## Rolling back the database

Treat this separately; it is not always possible.

- Migrations here add tables and columns. Going back to older code usually works **without** undoing them,
  because older code ignores what it does not know. Check the migration before assuming so.
- `alembic downgrade` is **not** a routine tool. Downgrading drops the newer tables and columns and the data
  in them. Migration `0003` refuses to downgrade while customer or employee accounts, newer booking statuses
  or imported menu items exist, precisely so it cannot silently discard them.
- If a migration damaged data, the recovery path is **restore the pre-release backup** (above), accepting the
  loss of anything recorded since. This is why a backup before each release is mandatory.
- Before any migration that changes or removes existing columns, rehearse it on a restored copy of
  production (the restore rehearsal gives you one) and write its recovery steps down first.

## Monitoring

Not set up; these need accounts the owner has not chosen.

| What | How |
|---|---|
| Uptime | An external monitor (UptimeRobot, Better Stack, Healthchecks…) requesting `https://YOUR-DOMAIN/api/ready` every 1–5 minutes, alerting by email or SMS. `ready` covers the API, the database and the schema version |
| Certificate | The same monitor's HTTPS-expiry alert. Caddy renews automatically; the alert catches a failure |
| Errors | `dc logs backend` shows unexpected errors as `unhandled error` with a stack trace (no request bodies). For alerts, add an error tracker such as Sentry; that needs a small code change and a decision about what data may leave the server |
| Disk | Alert when the server's disk passes about 80%. Photos are in the image; the database and logs are what grow |
| Backups | Alert if no new file appears in the off-server location for 26 hours |

## Logs

- Container logs are capped by Compose at 10 MB × 5 files per service, so they cannot fill the disk.
- API logs contain request paths and status codes, booking references and activity, but not names, phone
  numbers, emails, passwords or tokens. Reset and setup tokens travel in the URL fragment and in request
  bodies, neither of which is logged.
- Caddy's access log records visitor IP addresses and paths. IP addresses are personal data: include them in
  the retention decision.
- View: `dc logs --since 1h backend`, `dc logs --since 1h web`.

## Housekeeping

- Expired rate-limit records are cleared automatically as the limiter is used. To clear them by hand:
  `dc exec backend python -m app.cli purge-rate-limits`.
- Expired sessions are removed whenever anyone signs in.

## Proposed data-retention policy (needs the owner's approval; nothing is enabled)

No data is deleted automatically today. This is a proposal to react to, not a rule in force.

| Data | Proposed retention | Reason |
|---|---|---|
| Guest requests (no account): name, phone, email, notes | Delete or anonymise 12 months after the requested date | Enough for a returning guest or a dispute; no reason to keep longer |
| Customer accounts | Keep while active; delete on request; consider removing after 24 months without sign-in, with notice | The customer chose to have an account |
| Bookings linked to accounts | Same as the account; anonymise when the account is deleted | Keeps counts for the owner without personal data |
| Internal notes | Same as their booking | They can contain personal remarks |
| Activity log | 24 months | Accountability for staff actions |
| Proxy access logs (IP addresses) | 30 days (the 10 MB × 5 cap usually keeps far less) | Troubleshooting and abuse only |
| Backups | 14 daily + 8 weekly | A deleted record persists in backups until they age out; say so in the privacy notice |
| Employee accounts | Deactivate on leaving; delete after 12 months | The activity log keeps the name as text |

Before enabling any of this the owner should confirm the periods, check what Nepali law and the shop's
accountant require, and publish a short privacy notice. Implementing it means a scheduled job and tests; it
has not been built.

## Handling a request to delete someone's data

Until a retention job exists: find the person's bookings in the dashboard, and ask the developer to remove
them and (if any) the account from the database. Record that it was done. Remember backups hold copies
until they expire.
