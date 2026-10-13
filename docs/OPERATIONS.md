# Operations: backups, recovery, monitoring, logs, retention

`dc` means `docker compose -f docker-compose.prod.yml --env-file .env.production`.

## Backups

**Status: the tooling is ready and was tested with synthetic data. No backup is scheduled and none is
copied off any server, because no server or storage account exists yet. Scheduled operation and off-server
delivery are NOT VERIFIED. Do not assume backups are running until both are set up and checked.**

### How it works

`scripts/backup.sh` pipes `pg_dump` straight into `gpg`, encrypting to a **public** key. The unencrypted
dump never touches the disk. The server holds only the public key, so someone who takes over the server, or
obtains a backup file, cannot read the backups. The script refuses to run without a key.

Each run writes `backups/wendy-<UTC time>.dump.gpg` and a `.sha256` checksum, readable only by the user who
ran it. If an off-server destination is configured it copies both there; if not, it prints a warning that
the backup exists only on that server.

### One-time setup

1. **Create the backup key pair on a trusted computer that is not the server** (the owner's or developer's
   own machine):

   ```bash
   gpg --quick-generate-key "Wendy Juice Shop backups" default default never
   gpg --armor --export "Wendy Juice Shop backups" > backup-public-key.asc
   ```

   Protect the private key with a strong passphrase when prompted.
2. **Store the private key in two separate safe places** (see "Key recovery" below). Without it, no backup
   can ever be restored.
3. Copy **only** `backup-public-key.asc` to the server, for example to `/etc/wendy/`.
4. On the server: `cp .env.backup.example .env.backup` and set `BACKUP_GPG_RECIPIENT_FILE`.
5. Run `scripts/backup.sh` once and confirm a `.dump.gpg` file appears.
6. Copy that file to the computer holding the private key and run
   `scripts/restore-rehearsal.sh <file>` there. Only a successful rehearsal proves the backup is usable.

### Off-server copies (NOT VERIFIED: needs a storage account)

Install `rclone` on the server, configure a remote with write access to one bucket or folder (its
credentials live in rclone's own config file, mode 600, never in this repository), and set
`BACKUP_RCLONE_REMOTE=remote:path` in `.env.backup`. Prefer a destination that cannot be deleted or
overwritten by the server's credentials (object-lock or append-only), so an intruder on the server cannot
destroy the backups. The copy step is implemented but has never been run against real storage.

### Scheduling (NOT VERIFIED: needs a server)

Example units are in `deploy/systemd/`. After adjusting the user and path:

```bash
sudo cp deploy/systemd/wendy-backup.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now wendy-backup.timer
systemctl list-timers wendy-backup.timer          # confirm the next run
journalctl -u wendy-backup --since yesterday       # confirm the last run and its result
```

Or with cron: `15 21 * * * cd /srv/wendy-nepal && scripts/backup.sh >> /var/log/wendy-backup.log 2>&1`
(21:15 UTC is 03:00 in Pokhara). Also run it before every release. A failed run exits non-zero; add an alert
on failure or on "no new backup for 26 hours".

### Key recovery

- The private key is the only way to read backups. **If it is lost, every existing backup is unreadable.**
- Keep two copies in different places, for example an encrypted export in the owner's password manager and
  an offline copy (USB drive or printed `paperkey`) kept somewhere safe. Record who holds them.
- Export for safekeeping: `gpg --armor --export-secret-keys "Wendy Juice Shop backups" > backup-private-key.asc`.
  This file is as sensitive as the customer data itself. Never email it, never put it on the server or in git.
- Test recovery once: on a second computer, import the stored copy (`gpg --import backup-private-key.asc`)
  and run a restore rehearsal.
- **If the private key may have been exposed:** generate a new pair, replace the public key on the server,
  take a fresh backup, and delete or re-encrypt the old backups, because they are readable with the exposed key.

### Retention

`BACKUP_KEEP_DAYS` deletes local copies older than that many days. It is empty by default: nothing is
deleted until the owner approves a period (see the proposal below). Off-server retention is set on the
storage side.

## Restore rehearsal (safe, do it regularly)

```bash
scripts/restore-rehearsal.sh backups/wendy-<time>.dump.gpg
```

Run it where the private key is available. It checks the checksum, decrypts in memory, restores into a
throwaway PostgreSQL container, prints row counts and removes the container. It never touches the real
database and never writes the decrypted data to disk.

Tested on 13 Oct 2026 with synthetic data on a disposable database: an encrypted backup was restored with
matching rows; the same file could not be decrypted without the private key; a file altered after backup was
rejected by the checksum; running without a key configured wrote nothing.

## Restoring for real

Only when the production database is lost or corrupted. **This replaces current data with the backup.**

```bash
dc stop backend web                                  # stop writes
scripts/backup.sh                                    # if the database still answers, keep what is there (encrypted)
dc exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
# Decrypt where the private key is, and stream the result to the server over SSH (nothing decrypted is stored):
gpg --decrypt backups/wendy-<time>.dump.gpg | ssh SERVER \
  'cd /srv/wendy-nepal && docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db \
   sh -c "pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --no-owner --exit-on-error"'
dc run --rm migrate                                  # bring an older backup up to the current schema
dc up -d
curl -fsS https://YOUR-DOMAIN/api/ready
```

The decrypt-and-stream command above has not been run against a real server; rehearse it on a test server
first. Anything recorded after the backup was taken is lost; tell the owner which period that is so bookings made
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
- **Unexpected errors** appear as one line:
  `ERROR wendy.errors unhandled error id=<12 hex> <METHOD> <route> type=<exception> ... at=<file:line function ...>`.
  For database errors it adds the SQLSTATE and the table, column and constraint names. It never includes the
  exception text or statement values, because those can quote customer data. The visitor is shown the same
  `id` as "reference", so a report can be matched to the line: `dc logs backend | grep id=<reference>`.
- **PostgreSQL's own log** is set (in `docker-compose.prod.yml`) not to echo failing statements
  (`log_min_error_statement=panic`) and to omit DETAIL lines (`log_error_verbosity=terse`), both of which
  otherwise quote row values. If the database is ever moved to a managed service, set the same two options there.
- The command-line tool (`python -m app.cli ...`) prints errors to the operator's terminal, not to the log.
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
| Backups (encrypted) | 14 daily + 8 weekly | A deleted record persists in backups until they age out; say so in the privacy notice |
| Employee accounts | Deactivate on leaving; delete after 12 months | The activity log keeps the name as text |

Before enabling any of this the owner should confirm the periods, check what Nepali law and the shop's
accountant require, and publish a short privacy notice. Implementing it means a scheduled job and tests; it
has not been built.

## Handling a request to delete someone's data

Until a retention job exists: find the person's bookings in the dashboard, and ask the developer to remove
them and (if any) the account from the database. Record that it was done. Remember backups hold copies
until they expire.
