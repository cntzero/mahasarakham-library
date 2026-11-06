#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.';exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
export PYTHONPATH=/opt/maha-library-api/music-vendor
api=(music.py music_grouping.py music_merges.py personal_library.py server.py)
site=(music.js music.css music.html favorites.html favorites.js personal.css)
for file in "${api[@]}"; do test -s "$stage/$file";done
for file in "${site[@]}"; do test -s "$stage/site/$file";done
python3 "$stage/test_music_merges.py"
python3 "$stage/test_music_cache.py"
python3 "$stage/test_personal_library.py"
backup=$(mktemp -d /mnt/data/backups/library-smart-music-XXXXXXXX)
chmod 700 "$backup";mkdir "$backup/api" "$backup/site"
for file in "${api[@]}"; do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/$file";done
for file in "${site[@]}";do cp -a "$live/$file" "$backup/site/$file";done
python3 - "$backup/catalog.sqlite" <<'PY'
import sqlite3,sys
with sqlite3.connect('/mnt/data/survival-library/music/catalog.sqlite') as source,sqlite3.connect(sys.argv[1]) as backup:source.backup(backup)
PY
rollback(){
 trap - ERR
 for file in "${api[@]}";do if [[ -f "$backup/api/$file" ]];then cp -a "$backup/api/$file" "/opt/maha-library-api/$file";else rm -f "/opt/maha-library-api/$file";fi;done
 for file in "${site[@]}";do cp -a "$backup/site/$file" "$live/$file";done
 systemctl restart maha-library-api.service || true
 echo "Previous application restored; additive database fields retained. Backup: $backup" >&2;exit 1
}
trap rollback ERR
for file in "${api[@]}";do install -m 644 "$stage/$file" "/opt/maha-library-api/$file.new";mv -f "/opt/maha-library-api/$file.new" "/opt/maha-library-api/$file";done
runuser -u vhenderson -- env PYTHONPATH=/opt/maha-library-api/music-vendor python3 -c "import sys;sys.path.insert(0,'/opt/maha-library-api');import music_merges;music_merges.connect().close()"
for file in "${site[@]}";do install -m 644 "$stage/site/$file" "$live/$file.new";mv -f "$live/$file.new" "$live/$file";done
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20};do
 if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("albumMerges")' 2>/dev/null;then ready=true;break;fi
 sleep 1
done
[[ "$ready" == true ]]
trap - ERR
echo 'Album drag merging with undo, smart catalog caching, Liked Songs and playlist filters, and Favorites artwork installed. Refresh with Ctrl+F5.'
echo 'Album files and original MP3 tags are retained.'
echo "Backup: $backup"
