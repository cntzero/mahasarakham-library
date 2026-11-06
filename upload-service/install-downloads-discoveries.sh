#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
export PYTHONPATH=/mnt/data/projects/maha-library/music-vendor
python3 "$stage/test_music_downloads.py"
backup=$(mktemp -d /mnt/data/backups/library-downloads-discoveries-XXXXXXXX)
chmod 700 "$backup"
mkdir "$backup/api" "$backup/site"
api=(server.py music.py music_downloads.py)
site=(music.html music.js music.css knowledge.html knowledge.js knowledge-discoveries.js discovery.css)
for file in "${api[@]}"; do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/$file"; done
for file in "${site[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/site/$file"; done
rollback(){
 trap - ERR
 for file in "${api[@]}"; do if [[ -f "$backup/api/$file" ]]; then cp -a "$backup/api/$file" "/opt/maha-library-api/$file"; else rm -f "/opt/maha-library-api/$file"; fi; done
 for file in "${site[@]}"; do if [[ -f "$backup/site/$file" ]]; then cp -a "$backup/site/$file" "$live/$file"; else rm -f "$live/$file"; fi; done
 systemctl restart maha-library-api.service || true
 echo "Update failed; previous application restored. Backup: $backup" >&2
 exit 1
}
trap rollback ERR
for file in "${api[@]}"; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file"; done
for file in "${site[@]}"; do install -m 644 "$stage/site/$file" "$live/$file"; done
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20}; do if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("musicDownloads") and d.get("musicDiscoveries")' 2>/dev/null; then ready=true;break;fi;sleep 1;done
[[ "$ready" == true ]]
trap - ERR
echo 'Song/album downloads, Knowledge Daily Discoveries and faster Music discoveries installed.'
echo "Backup: $backup"
