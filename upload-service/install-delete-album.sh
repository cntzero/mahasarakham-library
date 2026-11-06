#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.';exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
export PYTHONPATH=/opt/maha-library-api/music-vendor
python3 "$stage/test_album_delete.py"
python3 "$stage/test_music_bulk.py"
backup=$(mktemp -d /mnt/data/backups/library-delete-album-XXXXXXXX)
chmod 700 "$backup"
cp -a /opt/maha-library-api/music_bulk.py "$backup/music_bulk.py"
for file in music.html music.js music.css;do test -s "$stage/site/$file";cp -a "$live/$file" "$backup/$file";done
rollback(){
 trap - ERR
 cp -a "$backup/music_bulk.py" /opt/maha-library-api/music_bulk.py
 for file in music.html music.js music.css;do cp -a "$backup/$file" "$live/$file";done
 systemctl restart maha-library-api.service || true
 echo "Previous application restored. Backup: $backup" >&2;exit 1
}
trap rollback ERR
install -m 644 "$stage/music_bulk.py" /opt/maha-library-api/music_bulk.py.new
mv -f /opt/maha-library-api/music_bulk.py.new /opt/maha-library-api/music_bulk.py
for file in music.js music.css music.html;do install -m 644 "$stage/site/$file" "$live/$file.new";mv -f "$live/$file.new" "$live/$file";done
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20};do
 if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("music")' 2>/dev/null;then ready=true;break;fi
 sleep 1
done
[[ "$ready" == true ]]
trap - ERR
echo 'Delete album is available in the album dialog for super users. Refresh with Ctrl+F5.'
echo 'Deletion requires a full album preview and typed confirmation. This installer deletes no media.'
echo "Backup: $backup"
