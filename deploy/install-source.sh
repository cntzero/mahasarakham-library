#!/usr/bin/env bash
# Fresh-host preparation only; services are not started here.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
: "${MAHA_SERVICE_USER:=maha}"
: "${MAHA_LAN_IP:?Set the server LAN IPv4 address}"
: "${MAHA_LAN_CIDR:?Set the allowed LAN subnet}"
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
[[ ! -e /srv/www/maha-library/current && ! -L /srv/www/maha-library/current ]] || { echo 'Existing installation found. Stopped; use the update procedure.'; exit 1; }
id "$MAHA_SERVICE_USER" >/dev/null
python3 - "$MAHA_LAN_IP" "$MAHA_LAN_CIDR" <<'PY'
import ipaddress,sys
ipaddress.IPv4Address(sys.argv[1]);ipaddress.IPv4Network(sys.argv[2],strict=False)
PY
install -d /opt/maha-library-api /srv/www/maha-library/releases /mnt/data/backups
for path in /srv/maha-library-api /mnt/data/survival-library/imported-books /mnt/data/survival-library/music /mnt/data/projects/maha-library/windows-music-import; do
 install -d -o "$MAHA_SERVICE_USER" -g "$MAHA_SERVICE_USER" "$path"
done
chmod 700 /srv/maha-library-api
install -m 644 "$repo"/upload-service/*.py /opt/maha-library-api/
release=$(mktemp -d /srv/www/maha-library/releases/source-XXXXXXXX)
cp -a "$repo/dist" "$release/dist"
for name in catalog.json archive-pages.json; do [[ -e "$release/dist/$name" ]] || printf '[]\n' >"$release/dist/$name"; done
[[ -e "$repo/asset-map.json" ]] || cp "$repo/asset-map.example.json" "$repo/asset-map.json"
ln -s "$release" /srv/www/maha-library/current
export MAHA_SERVICE_USER MAHA_LAN_IP MAHA_LAN_CIDR
python3 - "$repo" <<'PY'
from pathlib import Path
import os,sys
r=Path(sys.argv[1]);replacements={'@SERVICE_USER@':os.environ['MAHA_SERVICE_USER'],'@LAN_IP@':os.environ['MAHA_LAN_IP'],'@LAN_CIDR@':os.environ['MAHA_LAN_CIDR']}
for name in ['maha-library-api.service','maha-music-identification.service','maha-music-artwork.service']:
 text=(r/'deploy/systemd'/name).read_text()
 for a,b in replacements.items():text=text.replace(a,b)
 Path('/etc/systemd/system',name).write_text(text)
text=(r/'deploy/maha-library.nginx.conf.example').read_text()
for a,b in replacements.items():text=text.replace(a,b)
Path('/etc/nginx/sites-available/maha-library').write_text(text)
PY
systemctl daemon-reload
echo 'Prepared. Initialize your first account, TLS, and Nginx using docs/SERVER-SETUP.md. Services have not been started.'
