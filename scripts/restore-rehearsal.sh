#!/usr/bin/env bash
# Prove a backup file can be restored, without touching any real database.
# Restores it into a throwaway PostgreSQL container, prints row counts, removes it.
#
#   scripts/restore-rehearsal.sh backups/wendy-20261013T120000Z.dump.gpg
#
# For an encrypted backup (.gpg) this must run where the PRIVATE key is
# available to gpg (set GNUPGHOME if it is not in the default keyring). The
# decrypted data is piped straight into the throwaway database; it is not
# written to disk.
set -euo pipefail
file="${1:?Usage: scripts/restore-rehearsal.sh <backup.dump[.gpg]>}"
[ -s "$file" ] || { echo "No such backup file: $file" >&2; exit 1; }

if [ -f "$file.sha256" ]; then
  ( cd "$(dirname "$file")" && sha256sum --quiet -c "$(basename "$file").sha256" ) || { echo "Checksum mismatch: the file is damaged or was altered" >&2; exit 1; }
  echo "Checksum matches."
fi

name="wendy-restore-rehearsal-$$"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --tmpfs /var/lib/postgresql -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=rehearsal postgres:18 >/dev/null
i=0
until docker exec "$name" psql -U postgres -d rehearsal -qAtc 'select 1' >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "Throwaway database did not start" >&2; exit 1; }
  sleep 1
done

restore() { docker exec -i "$name" pg_restore -U postgres -d rehearsal --no-owner --exit-on-error; }
case "$file" in
  *.gpg) gpg --batch --quiet --decrypt "$file" | restore ;;
  *)     restore < "$file" ;;
esac

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
