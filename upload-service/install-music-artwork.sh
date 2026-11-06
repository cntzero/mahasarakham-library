#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
export PYTHONPATH=/mnt/data/projects/maha-library/music-vendor
python3 "$stage/test_music_art.py"
python3 "$stage/test_music_http.py"
backup=$(mktemp -d /mnt/data/backups/library-music-artwork-XXXXXXXX)
chmod 700 "$backup"
mkdir "$backup/api" "$backup/site"
api=(server.py music.py music_art.py music_art_worker.py)
for file in "${api[@]}"; do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/"; done
for file in music.html music.js music.css; do cp -a "$live/$file" "$backup/site/"; done
unit=/etc/systemd/system/maha-music-artwork.service
[[ ! -f "$unit" ]] || cp -a "$unit" "$backup/artwork.service"
was_active=$(systemctl is-active maha-music-artwork.service || true)
was_enabled=$(systemctl is-enabled maha-music-artwork.service 2>/dev/null || true)
python3 - "$backup/catalog.sqlite" <<'PY'
import sqlite3,sys
with sqlite3.connect('/mnt/data/survival-library/music/catalog.sqlite') as source,sqlite3.connect(sys.argv[1]) as destination:source.backup(destination)
PY
rollback(){
 trap - ERR
 systemctl stop maha-music-artwork.service || true
 for file in "${api[@]}"; do if [[ -f "$backup/api/$file" ]]; then cp -a "$backup/api/$file" "/opt/maha-library-api/$file"; else rm -f "/opt/maha-library-api/$file"; fi; done
 for file in music.html music.js music.css; do cp -a "$backup/site/$file" "$live/$file"; done
 if [[ -f "$backup/artwork.service" ]]; then cp -a "$backup/artwork.service" "$unit"; else systemctl disable maha-music-artwork.service || true; rm -f "$unit"; fi
 systemctl daemon-reload
 systemctl restart maha-library-api.service || true
 [[ "$was_enabled" != enabled ]] || systemctl enable maha-music-artwork.service || true
 [[ "$was_active" != active ]] || systemctl start maha-music-artwork.service || true
 echo "Artwork installation failed; previous application restored. Backup: $backup" >&2
 exit 1
}
trap rollback ERR
for file in "${api[@]}"; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file"; done
for file in music.html music.js music.css; do install -m 644 "$stage/site/$file" "$live/$file"; done
# Initialise the additive schema before API and worker start concurrently.
python3 - "$stage" <<'PY'
import sys
sys.path.insert(0,sys.argv[1])
import music_art
with music_art.connect():pass
PY
cat > "$unit" <<'UNIT'
[Unit]
Description=MAHA album artwork lookup and offline fallback
After=network.target maha-library-api.service
RequiresMountsFor=/mnt/data/survival-library/music
[Service]
User=vhenderson
Group=vhenderson
ExecStart=/usr/bin/python3 /opt/maha-library-api/music_art_worker.py
Environment=PYTHONPATH=/opt/maha-library-api/music-vendor
Restart=on-failure
RestartSec=10
UMask=0022
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/mnt/data/survival-library/music
MemoryMax=768M
TasksMax=32
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20}; do if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("music")' 2>/dev/null; then ready=true;break;fi;sleep 1;done
[[ "$ready" == true ]]
systemctl enable maha-music-artwork.service
systemctl restart maha-music-artwork.service
systemctl is-active --quiet maha-music-artwork.service
trap - ERR
echo 'Artwork tools installed. Music → Find missing artwork starts the bulk lookup.'
echo 'Album → Change artwork reviews matches; Upload artwork accepts your own JPEG or PNG.'
echo "Backup: $backup"
