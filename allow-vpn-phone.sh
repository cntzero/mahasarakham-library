#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
config=$(readlink -f /etc/nginx/sites-enabled/maha-library)
backup=$(mktemp -d /mnt/data/backups/library-vpn-access-XXXXXXXX)
cp -a "$config" "$backup/nginx.conf"
python3 - "$config" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
if 'allow 10.5.5.2;' not in s:
    anchor='    allow 192.168.1.0/24;'
    if anchor not in s:raise SystemExit('Expected LAN rule not found; no changes made.')
    s=s.replace(anchor,anchor+'\n    allow 10.5.5.2; # First authorized WireGuard device',1)
    p.write_text(s)
PY
if ! nginx -t; then cp "$backup/nginx.conf" "$config"; exit 1; fi
if ! systemctl reload nginx; then
    cp "$backup/nginx.conf" "$config"
    nginx -t && systemctl reload nginx
    exit 1
fi
printf 'Library now allows VPN device 10.5.5.2.\nBackup: %s\nRefresh the library on your phone while using cellular + WireGuard.\n' "$backup"
