#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
files=(index.html knowledge.html add-books.html archives.html access.html access-procedure.html users.html login.html reader.html archive-reader.html session.js session.css maha.css login.js)
backup=$(mktemp -d /mnt/data/backups/library-stable-header-XXXXXXXX)
for file in "${files[@]}"; do cp -a "$live/$file" "$backup/"; done
rollback(){ trap - ERR; for file in "${files[@]}"; do cp -a "$backup/$file" "$live/$file"; done; echo "Update failed; previous files restored from $backup" >&2; exit 1; }
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$live/$file"; done
grep -q 'maha-session-slot' "$live/index.html"
grep -q 'maha-session-slot' "$live/knowledge.html"
nginx -t
trap - ERR
echo "Stable header and login recovery installed. Backup: $backup"
