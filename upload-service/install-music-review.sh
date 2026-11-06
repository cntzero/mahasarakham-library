#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
api=(music_grouping.py music.py music_bulk.py music_art_worker.py music_tag_worker.py)
for file in "${api[@]}"; do test -s "$stage/$file"; done
for file in music.html music.js; do test -s "$stage/site/$file"; done
export PYTHONPATH=/opt/maha-library-api/music-vendor
python3 "$stage/test_review_regressions.py"
python3 "$stage/test_music_bulk.py"
backup=$(mktemp -d /mnt/data/backups/library-music-review-XXXXXXXX)
chmod 700 "$backup"
mkdir "$backup/api" "$backup/site"
for file in "${api[@]}"; do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/$file"; done
for file in music.html music.js; do cp -a "$live/$file" "$backup/site/$file"; done
art_active=$(systemctl is-active maha-music-artwork.service || true)
rollback(){
 trap - ERR
 for file in "${api[@]}"; do
  if [[ -f "$backup/api/$file" ]]; then cp -a "$backup/api/$file" "/opt/maha-library-api/$file"; else rm -f "/opt/maha-library-api/$file"; fi
 done
 for file in music.html music.js; do cp -a "$backup/site/$file" "$live/$file"; done
 systemctl restart maha-library-api.service || true
 [[ "$art_active" != active ]] || systemctl restart maha-music-artwork.service || true
 echo "Update failed; previous application restored. Backup: $backup" >&2
 exit 1
}
trap rollback ERR
# Replace each code file atomically; an ongoing import is left running.
for file in "${api[@]}"; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file.new"; mv -f "/opt/maha-library-api/$file.new" "/opt/maha-library-api/$file"; done
PYTHONPATH=/opt/maha-library-api/music-vendor python3 -c "import sys;sys.path.insert(0,'/opt/maha-library-api');import music;music.connect().close()"
for file in music.js music.html; do install -m 644 "$stage/site/$file" "$live/$file.new"; mv -f "$live/$file.new" "$live/$file"; done
systemctl restart maha-library-api.service
[[ "$art_active" != active ]] || systemctl restart maha-music-artwork.service
ready=false
for attempt in {1..20}; do
 if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("music")' 2>/dev/null; then ready=true;break;fi
 sleep 1
done
[[ "$ready" == true ]]
trap - ERR
echo 'Reviewed music grouping, duplicate access, artwork matching and bulk deletion fixes installed.'
echo 'Refresh Music with Ctrl+F5. Collection > Duplicate files shows all verified copies. No files were deleted.'
echo "Backup: $backup"
