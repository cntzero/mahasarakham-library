#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
project=/mnt/data/projects/maha-library
live=$(readlink -f /srv/www/maha-library/current)/dist
config=$(readlink -f /etc/nginx/sites-enabled/maha-library)
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
PYTHONPATH="$project/music-vendor" python3 "$stage/test_music.py"
PYTHONPATH="$project/music-vendor" python3 "$stage/test_music_http.py"
backup=$(mktemp -d /mnt/data/backups/library-music-XXXXXXXX);chmod 700 "$backup"
mkdir "$backup/site" "$backup/api"
files=(index.html knowledge.html archives.html access.html music.html music.js music.css)
for file in "${files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/site/"; done
for file in server.py music.py music_tag_worker.py; do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/"; done
cp -a "$config" "$backup/nginx.conf"
override=/etc/systemd/system/maha-library-api.service.d/music.conf
[[ ! -f "$override" ]] || cp -a "$override" "$backup/music.conf"
rollback(){ trap - ERR; for file in "${files[@]}"; do if [[ -f "$backup/site/$file" ]]; then cp -a "$backup/site/$file" "$live/$file"; else rm -f "$live/$file"; fi; done; for file in server.py music.py music_tag_worker.py; do if [[ -f "$backup/api/$file" ]]; then cp -a "$backup/api/$file" "/opt/maha-library-api/$file"; else rm -f "/opt/maha-library-api/$file"; fi; done; cp -a "$backup/nginx.conf" "$config"; if [[ -f "$backup/music.conf" ]]; then cp -a "$backup/music.conf" "$override"; else rm -f "$override"; fi; systemctl daemon-reload; systemctl restart maha-library-api.service || true; nginx -t && systemctl reload nginx || true; echo "Installation failed; prior application restored. Music copies retained. Backup: $backup" >&2; exit 1; }
trap rollback ERR
install -d /opt/maha-library-api/music-vendor
cp -a "$project/music-vendor/." /opt/maha-library-api/music-vendor/
for file in server.py music.py music_tag_worker.py; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file"; done
for file in "${files[@]}"; do install -m 644 "$stage/site/$file" "$live/$file"; done
install -d /mnt/data/survival-library/music /etc/systemd/system/maha-library-api.service.d
cat > "$override" <<'UNIT'
[Service]
Environment=PYTHONPATH=/opt/maha-library-api/music-vendor
ReadWritePaths=/mnt/data/survival-library/music
UNIT
python3 - "$config" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
if '# BEGIN MAHA MUSIC' not in s:
 block='''    # BEGIN MAHA MUSIC
    location /music-media/tracks/ {
        alias /mnt/data/survival-library/music/tracks/;
        autoindex off;
        types { audio/mpeg mp3; }
        limit_except GET { deny all; }
        add_header X-Content-Type-Options nosniff always;
    }
    location /music-media/covers/ {
        alias /mnt/data/survival-library/music/covers/;
        autoindex off;
        types { image/jpeg jpg; }
        limit_except GET { deny all; }
        add_header X-Content-Type-Options nosniff always;
    }
    # END MAHA MUSIC
'''
 s=s.replace('    location / {',block+'    location / {',1);p.write_text(s)
PY
nginx -t
systemctl daemon-reload
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20}; do if curl -fsS http://127.0.0.1:8123/api/library/health | python3 -c 'import json,sys;assert json.load(sys.stdin).get("music")' 2>/dev/null; then ready=true;break;fi;sleep 1;done
[[ "$ready" == true ]]
systemctl reload nginx
trap - ERR
echo "Music library, signed-in uploads, owner/super metadata editing and local AI tags enabled: https://192.168.1.64/music.html"
echo "Backup: $backup"
