#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
for file in music.html music.js music.css; do test -s "$stage/$file"; done
backup=$(mktemp -d /mnt/data/backups/library-player-album-XXXXXXXX)
chmod 700 "$backup"
for file in music.html music.js music.css; do cp -a "$live/$file" "$backup/$file"; done
rollback(){ trap - ERR; for file in music.html music.js music.css; do cp -a "$backup/$file" "$live/$file"; done; echo "Previous pages restored. Backup: $backup" >&2; exit 1; }
trap rollback ERR
for file in music.js music.css music.html; do install -m 644 "$stage/$file" "$live/$file.new"; mv -f "$live/$file.new" "$live/$file"; cmp "$stage/$file" "$live/$file"; done
trap - ERR
echo 'Playing artwork and track title now open the album track list. Refresh Music with Ctrl+F5.'
echo "Backup: $backup"
