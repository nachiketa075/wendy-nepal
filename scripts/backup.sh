#!/usr/bin/env sh
# Write a compressed PostgreSQL backup of the running stack to ./backups/.
#
#   scripts/backup.sh                       # production stack (.env.production)
#   COMPOSE_ARGS="" scripts/backup.sh       # local development stack (.env)
#
# The file contains customer names, phone numbers and emails. Keep it private,
# copy it off the server, and never commit it (backups/ is git-ignored).
set -eu
cd "$(dirname "$0")/.."
: "${COMPOSE_ARGS=-f docker-compose.prod.yml --env-file .env.production}"
mkdir -p backups
chmod 700 backups
file="backups/wendy-$(date -u +%Y%m%dT%H%M%SZ).dump"
umask 077
# shellcheck disable=SC2086
docker compose $COMPOSE_ARGS exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' > "$file"
[ -s "$file" ] || { echo "Backup failed: $file is empty" >&2; rm -f "$file"; exit 1; }
echo "Backup written: $file ($(du -h "$file" | cut -f1))"
