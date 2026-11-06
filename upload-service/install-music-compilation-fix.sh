#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
backup=$(mktemp -d /mnt/data/backups/library-compilation-grouping-XXXXXXXX)
chmod 700 "$backup"
cp -a /opt/maha-library-api/music.py "$backup/music.py"
for file in music.js music.html; do cp -a "$live/$file" "$backup/$file"; done
rollback(){ trap - ERR; cp -a "$backup/music.py" /opt/maha-library-api/music.py; for file in music.js music.html; do cp -a "$backup/$file" "$live/$file"; done; systemctl restart maha-library-api.service || true; echo "Previous files restored: $backup" >&2; exit 1; }
trap rollback ERR
install -m 644 "$stage/music.py" /opt/maha-library-api/music.py
for file in music.js music.html; do install -m 644 "$stage/site/$file" "$live/$file"; done
systemctl restart maha-library-api.service
trap - ERR
echo 'Year/genre compilation grouping installed. Refresh Music with Ctrl+F5.'
echo "Backup: $backup"
