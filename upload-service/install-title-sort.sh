#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
backup=$(mktemp -d /mnt/data/backups/library-title-sort-XXXXXXXX)
for file in book-dates.js catalog-state.js; do
 [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/"
 install -m 644 "$stage/$file" "$live/$file"
done
echo "Title A–Z is now the default. Shelf order removed. Backup: $backup"
