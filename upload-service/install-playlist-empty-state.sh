#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
api=(personal_library.py server.py)
site=(personal.js personal.css favorites.html favorites.js index.html library-tools.js music.html music.js knowledge.html knowledge.js archives.html archives.js reader.html archive-reader.html)
for file in "${api[@]}"; do test -s "$stage/$file"; done
for file in "${site[@]}"; do test -s "$stage/site/$file"; done
export PYTHONPATH=/opt/maha-library-api/music-vendor
python3 "$stage/test_personal_library.py"
backup=$(mktemp -d /mnt/data/backups/library-playlist-empty-XXXXXXXX)
chmod 700 "$backup";mkdir "$backup/api" "$backup/site"
for file in "${api[@]}"; do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/$file"; done
for file in "${site[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/site/$file"; done
rollback(){
 trap - ERR
 for file in "${api[@]}"; do if [[ -f "$backup/api/$file" ]]; then cp -a "$backup/api/$file" "/opt/maha-library-api/$file"; else rm -f "/opt/maha-library-api/$file"; fi; done
 for file in "${site[@]}"; do if [[ -f "$backup/site/$file" ]]; then cp -a "$backup/site/$file" "$live/$file"; else rm -f "$live/$file"; fi; done
 systemctl restart maha-library-api.service || true
 echo "Update failed; previous pages and service restored. Backup: $backup" >&2;exit 1
}
trap rollback ERR
# Install shared dependencies before pages and routes that use them.
for file in "${api[@]}"; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file.new";mv -f "/opt/maha-library-api/$file.new" "/opt/maha-library-api/$file"; done
for file in "${site[@]}"; do install -m 644 "$stage/site/$file" "$live/$file.new";mv -f "$live/$file.new" "$live/$file"; done
# Create private per-user collection storage as the existing application account.
runuser -u vhenderson -- env PYTHONPATH=/opt/maha-library-api/music-vendor python3 -c "import sys;sys.path.insert(0,'/opt/maha-library-api');import personal_library;personal_library.initialize()"
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20}; do
 if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("personalLibrary")' 2>/dev/null; then ready=true;break;fi
 sleep 1
done
[[ "$ready" == true ]]
trap - ERR
echo 'Empty playlist chooser removed. Create your first playlist directly. Refresh with Ctrl+F5.'
echo 'Games favorites will populate when the games catalog exists. Media files were not changed.'
echo "Backup: $backup"
