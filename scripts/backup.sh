#!/usr/bin/env bash
# Encrypted PostgreSQL backup of the running stack.
#
#   scripts/backup.sh
#
# Settings come from the environment or from .env.backup (see .env.backup.example).
# The dump is encrypted to a PUBLIC key as it is produced; the unencrypted dump
# never touches the disk, and this server never holds the private key, so the
# server alone cannot decrypt its own backups.
#
# A backup contains customer names, phone numbers, emails and password hashes.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env.backup ]; then
  set -a; . ./.env.backup; set +a
fi

: "${COMPOSE_ARGS=-f docker-compose.prod.yml --env-file .env.production}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
BACKUP_GPG_RECIPIENT_FILE="${BACKUP_GPG_RECIPIENT_FILE:-}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
BACKUP_DB_CONTAINER="${BACKUP_DB_CONTAINER:-}"       # a plain container instead of Compose (rehearsals)
BACKUP_ALLOW_PLAINTEXT="${BACKUP_ALLOW_PLAINTEXT:-}"  # "yes" = write an UNENCRYPTED dump (local development only)

fail() { echo "backup: $*" >&2; exit 1; }
log()  { echo "backup: $*"; }

DUMP='pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner'
dump() {
  if [ -n "$BACKUP_DB_CONTAINER" ]; then
    docker exec "$BACKUP_DB_CONTAINER" sh -c "$DUMP"
  else
    # shellcheck disable=SC2086
    docker compose $COMPOSE_ARGS exec -T db sh -c "$DUMP"
  fi
}

umask 077
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

if [ -n "$BACKUP_GPG_RECIPIENT_FILE" ]; then
  [ -r "$BACKUP_GPG_RECIPIENT_FILE" ] || fail "public key file not readable: $BACKUP_GPG_RECIPIENT_FILE"
  command -v gpg >/dev/null || fail "gpg is not installed"
  # A private scratch keyring for gpg's own bookkeeping. It holds no secret key.
  gpg_home="$BACKUP_DIR/.gnupg"
  mkdir -p "$gpg_home"; chmod 700 "$gpg_home"
  file="$BACKUP_DIR/wendy-$stamp.dump.gpg"
  dump | gpg --homedir "$gpg_home" --batch --yes --quiet --trust-model always \
             --recipient-file "$BACKUP_GPG_RECIPIENT_FILE" --encrypt --output "$file.partial"
  mode="encrypted"
elif [ "$BACKUP_ALLOW_PLAINTEXT" = "yes" ]; then
  file="$BACKUP_DIR/wendy-$stamp.dump"
  dump > "$file.partial"
  mode="UNENCRYPTED"
else
  fail "no encryption key configured. Set BACKUP_GPG_RECIPIENT_FILE (see .env.backup.example). Refusing to write an unencrypted backup."
fi

[ -s "$file.partial" ] || { rm -f -- "$file.partial"; fail "the dump is empty; nothing was kept"; }
if [ "$mode" = "encrypted" ] && [ "$(head -c 5 "$file.partial")" = "PGDMP" ]; then
  rm -f -- "$file.partial"; fail "output is not encrypted; nothing was kept"
fi
mv -- "$file.partial" "$file"
( cd "$BACKUP_DIR" && sha256sum "$(basename "$file")" > "$(basename "$file").sha256" )
log "$mode backup written: $file ($(du -h "$file" | cut -f1))"

if [ -n "$BACKUP_RCLONE_REMOTE" ]; then
  command -v rclone >/dev/null || fail "BACKUP_RCLONE_REMOTE is set but rclone is not installed; the backup exists only on this server"
  rclone copy --quiet "$file" "$BACKUP_RCLONE_REMOTE" && rclone copy --quiet "$file.sha256" "$BACKUP_RCLONE_REMOTE" \
    || fail "off-server copy FAILED; the backup exists only on this server"
  log "copied off-server to the configured remote"
else
  log "WARNING: no off-server destination configured (BACKUP_RCLONE_REMOTE). This backup exists only on this server."
fi

if [ -n "$BACKUP_KEEP_DAYS" ]; then
  case "$BACKUP_KEEP_DAYS" in (*[!0-9]*|'') fail "BACKUP_KEEP_DAYS must be a whole number";; esac
  # Only this script's own files, only directly inside the backup folder.
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'wendy-*.dump*' -mtime "+$BACKUP_KEEP_DAYS" -delete
  log "removed local backups older than $BACKUP_KEEP_DAYS days"
fi
