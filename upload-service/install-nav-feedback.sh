#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
files=(index.html knowledge.html archives.html add-books.html access.html access-procedure.html session.js maha.css)
backup=$(mktemp -d /mnt/data/backups/library-nav-feedback-XXXXXXXX)
for file in "${files[@]}"; do cp -a "$live/$file" "$backup/"; done
rollback(){ trap - ERR; for file in "${files[@]}"; do cp -a "$backup/$file" "$live/$file"; done; echo "Update failed; restored from $backup" >&2; exit 1; }
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$live/$file"; done
trap - ERR
echo "Direct Users link and navigation highlights installed. Backup: $backup"
