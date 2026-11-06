#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/ddns
python3 "$stage/test_update.py"
install -d -m 700 /etc/maha-vpn-ddns
python3 - <<'PY'
from pathlib import Path
import getpass,os
p=Path('/etc/maha-vpn-ddns/token')
prompt='Paste GoDaddy PAT (Enter keeps existing token): ' if p.exists() else 'Paste GoDaddy PAT (input is hidden): '
token=getpass.getpass(prompt).strip()
if not token and p.exists():raise SystemExit(0)
if not token or any(c.isspace() for c in token):raise SystemExit('No valid token entered; nothing enabled.')
tmp=p.with_suffix('.new');fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as out:out.write(token+'\n')
os.chmod(tmp,0o600);os.replace(tmp,p)
print('Token saved privately on MAHA.')
PY
install -d /opt/maha-vpn-ddns
install -m 644 "$stage/update.py" /opt/maha-vpn-ddns/update.py
echo 'Checking IP sources and GoDaddy access without changing DNS...'
python3 /opt/maha-vpn-ddns/update.py --check
cat >/etc/systemd/system/maha-vpn-ddns.service <<'UNIT'
[Unit]
Description=Keep vpn.discerntechnologies.com pointed at this home connection
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
DynamicUser=yes
LoadCredential=godaddy-pat:/etc/maha-vpn-ddns/token
StateDirectory=maha-vpn-ddns
ExecStart=/usr/bin/python3 /opt/maha-vpn-ddns/update.py
TimeoutStartSec=120
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
UNIT
cat >/etc/systemd/system/maha-vpn-ddns.timer <<'UNIT'
[Unit]
Description=Check home VPN DNS every five minutes
[Timer]
OnBootSec=90s
OnUnitActiveSec=5min
RandomizedDelaySec=15s
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl start maha-vpn-ddns.service
systemctl enable --now maha-vpn-ddns.timer
echo 'Automatic VPN DNS updates enabled (every five minutes).'
echo 'Only the existing vpn.discerntechnologies.com A record is managed.'
echo 'Renew the GoDaddy token before the expiration date shown in your GoDaddy account.'
systemctl list-timers maha-vpn-ddns.timer --no-pager
