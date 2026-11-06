#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
PYTHONPATH=/mnt/data/projects/maha-library/music-vendor python3 "$stage/test_music_http.py"
backup=$(mktemp -d /mnt/data/backups/library-music-sorting-XXXXXXXX)
chmod 700 "$backup"
for file in music.html music.js music.css; do cp -a "$live/$file" "$backup/$file"; done
for file in server.py music.py; do cp -a "/opt/maha-library-api/$file" "$backup/$file"; done
rollback(){ trap - ERR; for file in music.html music.js music.css; do cp -a "$backup/$file" "$live/$file"; done; for file in server.py music.py; do cp -a "$backup/$file" "/opt/maha-library-api/$file"; done; systemctl restart maha-library-api.service || true; echo "Update failed; previous Music application restored. Backup: $backup" >&2; exit 1; }
trap rollback ERR
for file in server.py music.py; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file"; done
for file in music.html music.js music.css; do install -m 644 "$stage/site/$file" "$live/$file"; done
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20}; do if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("music")' 2>/dev/null; then ready=true;break;fi;sleep 1;done
[[ "$ready" == true ]]
trap - ERR
echo 'Duration and file-size sorting installed, including removal and episode grouping. Original audio files are preserved.'
echo "Backup: $backup"
