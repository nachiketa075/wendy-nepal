#!/usr/bin/env sh
# Prove a backup file can be restored, without touching any real database.
# Restores it into a throwaway PostgreSQL container, prints row counts, removes it.
#
#   scripts/restore-rehearsal.sh backups/wendy-20261012T120000Z.dump
set -eu
file="${1:?Usage: scripts/restore-rehearsal.sh <backup.dump>}"
[ -s "$file" ] || { echo "No such backup file: $file" >&2; exit 1; }
name="wendy-restore-rehearsal-$$"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --tmpfs /var/lib/postgresql -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=rehearsal postgres:18 >/dev/null
i=0
until docker exec "$name" pg_isready -U postgres -d rehearsal >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "Throwaway database did not start" >&2; exit 1; }
  sleep 1
done
sleep 1
docker exec -i "$name" pg_restore -U postgres -d rehearsal --no-owner --exit-on-error < "$file"
echo "Restore succeeded. Row counts in the restored copy:"
docker exec "$name" psql -U postgres -d rehearsal -At -F ' = ' -c "
  SELECT 'migration', version_num FROM alembic_version
  UNION ALL SELECT 'accounts', count(*)::text FROM accounts
  UNION ALL SELECT 'bookings', count(*)::text FROM bookings
  UNION ALL SELECT 'booking_status_history', count(*)::text FROM booking_status_history
  UNION ALL SELECT 'menu_items', count(*)::text FROM menu_items
  UNION ALL SELECT 'menu_categories', count(*)::text FROM menu_categories
  UNION ALL SELECT 'booking_windows', count(*)::text FROM booking_windows
  UNION ALL SELECT 'activity_log', count(*)::text FROM activity_log"
echo "Throwaway database removed."
