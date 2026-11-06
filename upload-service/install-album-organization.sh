#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.';exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
api=(music_grouping.py music_merges.py music_identify.py)
site=(music.js music.html music-identify.js)
for file in "${api[@]}";do test -s "$stage/$file";done
for file in "${site[@]}";do test -s "$stage/site/$file";done
export PYTHONPATH=/opt/maha-library-api/music-vendor
python3 "$stage/test_album_organize.py"
python3 "$stage/test_music_merges.py"
backup=$(mktemp -d /mnt/data/backups/library-album-organization-XXXXXXXX)
chmod 700 "$backup";mkdir "$backup/api" "$backup/site"
for file in "${api[@]}";do cp -a "/opt/maha-library-api/$file" "$backup/api/$file";done
for file in "${site[@]}";do cp -a "$live/$file" "$backup/site/$file";done
rollback(){
 trap - ERR
 for file in "${api[@]}";do cp -a "$backup/api/$file" "/opt/maha-library-api/$file";done
 for file in "${site[@]}";do cp -a "$backup/site/$file" "$live/$file";done
 systemctl restart maha-library-api.service || true
 echo "Previous application restored. Backup: $backup" >&2;exit 1
}
trap rollback ERR
for file in "${api[@]}";do install -m 644 "$stage/$file" "/opt/maha-library-api/$file.new";mv -f "/opt/maha-library-api/$file.new" "/opt/maha-library-api/$file";done
for file in "${site[@]}";do install -m 644 "$stage/site/$file" "$live/$file.new";mv -f "$live/$file.new" "$live/$file";done
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20};do
 if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("music")' 2>/dev/null;then ready=true;break;fi
 sleep 1
done
[[ "$ready" == true ]]
trap - ERR
echo 'Unknown-album singles now share one collection. Rename album is available beside the album title. Refresh with Ctrl+F5.'
echo 'Multi-track unknown albums and manual groups stay separate. Original MP3 files are unchanged.'
echo "Backup: $backup"
