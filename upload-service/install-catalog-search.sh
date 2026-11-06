#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
files=(index.html maha.css book-dates.js catalog-state.js)
backup=$(mktemp -d /mnt/data/backups/library-catalog-search-XXXXXXXX)
for file in "${files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/"; done
rollback(){ trap - ERR; for file in "${files[@]}"; do [[ ! -f "$backup/$file" ]] || cp -a "$backup/$file" "$live/$file"; done; echo "Update failed; previous pages restored from $backup" >&2; exit 1; }
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$live/$file"; done
trap - ERR
echo "Search moved beside the catalog filters. Title A–Z is the default. Backup: $backup"
