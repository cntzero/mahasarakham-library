#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.';exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
api=(music_identify.py music_identify_worker.py server.py)
site=(music.js music.css music.html music-identify.js)
for file in "${api[@]}";do test -s "$stage/$file";done
for file in "${site[@]}";do test -s "$stage/site/$file";done
if ! command -v fpcalc >/dev/null;then
 apt-get update
 apt-get install -y --no-install-recommends libchromaprint-tools
fi
export PYTHONPATH=/opt/maha-library-api/music-vendor
python3 "$stage/test_music_identify.py"
backup=$(mktemp -d /mnt/data/backups/library-identification-XXXXXXXX)
chmod 700 "$backup";mkdir "$backup/api" "$backup/site"
for file in "${api[@]}";do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/$file";done
for file in "${site[@]}";do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/site/$file";done
unit=/etc/systemd/system/maha-music-identification.service
[[ ! -f "$unit" ]] || cp -a "$unit" "$backup/worker.service"
was_active=$(systemctl is-active maha-music-identification.service || true)
was_enabled=$(systemctl is-enabled maha-music-identification.service 2>/dev/null || true)
rollback(){
 trap - ERR
 systemctl stop maha-music-identification.service || true
 for file in "${api[@]}";do
  if [[ -f "$backup/api/$file" ]];then cp -a "$backup/api/$file" "/opt/maha-library-api/$file";fi
 done
 for file in "${site[@]}";do
  if [[ -f "$backup/site/$file" ]];then cp -a "$backup/site/$file" "$live/$file";fi
 done
 if [[ -f "$backup/worker.service" ]];then
  cp -a "$backup/worker.service" "$unit"
 else
  systemctl disable maha-music-identification.service || true
 fi
 systemctl daemon-reload;systemctl restart maha-library-api.service || true
 [[ "$was_enabled" != enabled ]] || systemctl enable maha-music-identification.service || true
 [[ "$was_active" != active ]] || systemctl start maha-music-identification.service || true
 echo "Previous existing application files restored. New inactive files and fingerprinting utility retained. Backup: $backup" >&2
 exit 1
}
trap rollback ERR
for file in "${api[@]}";do install -m 644 "$stage/$file" "/opt/maha-library-api/$file.new";mv -f "/opt/maha-library-api/$file.new" "/opt/maha-library-api/$file";done
for file in "${site[@]}";do install -m 644 "$stage/site/$file" "$live/$file.new";mv -f "$live/$file.new" "$live/$file";done
runuser -u vhenderson -- env PYTHONPATH=/opt/maha-library-api/music-vendor python3 -c "import sys;sys.path.insert(0,'/opt/maha-library-api');import music_identify;music_identify.connect().close()"
cat > "$unit" <<'UNIT'
[Unit]
Description=MAHA manual audio recognition and metadata review
After=network-online.target maha-library-api.service
Wants=network-online.target
RequiresMountsFor=/mnt/data/survival-library/music
[Service]
User=vhenderson
Group=vhenderson
ExecStart=/usr/bin/python3 /opt/maha-library-api/music_identify_worker.py
Environment=PYTHONPATH=/opt/maha-library-api/music-vendor
Restart=on-failure
RestartSec=10
UMask=0077
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
systemctl daemon-reload;systemctl restart maha-library-api.service
ready=false
for attempt in {1..20};do
 if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys;assert json.load(sys.stdin).get("musicIdentification")' 2>/dev/null;then ready=true;break;fi
 sleep 1
done
[[ "$ready" == true ]]
systemctl enable --now maha-music-identification.service
systemctl restart maha-music-identification.service
systemctl is-active --quiet maha-music-identification.service
trap - ERR
echo 'Identify & review installed. Refresh Music with Ctrl+F5, open an album, then Identify & review.'
echo 'One-time setup: enter an AcoustID APPLICATION API key in Recognition setup. No MP3s are uploaded; nothing applies automatically.'
echo 'Online recognition greys out when MAHA cannot reach the recognition services.'
echo "Backup: $backup"
