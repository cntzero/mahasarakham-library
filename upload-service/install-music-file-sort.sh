#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
for file in music.html music.js; do test -s "$stage/$file"; done
backup=$(mktemp -d /mnt/data/backups/library-music-file-sort-XXXXXXXX)
chmod 700 "$backup"
for file in music.html music.js; do cp -a "$live/$file" "$backup/$file"; done
rollback(){ trap - ERR; for file in music.html music.js; do cp -a "$backup/$file" "$live/$file"; done; echo "Update failed; previous Music interface restored. Backup: $backup" >&2; exit 1; }
trap rollback ERR
for file in music.html music.js; do install -m 644 "$stage/$file" "$live/$file"; done
cmp "$stage/music.js" "$live/music.js"
cmp "$stage/music.html" "$live/music.html"

trap - ERR
echo 'Individual-file sorting installed: https://192.168.1.64/music.html'
echo "Backup: $backup"
