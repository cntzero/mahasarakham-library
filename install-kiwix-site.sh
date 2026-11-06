#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
stage=/mnt/data/projects/maha-library
apt-get update
apt-get install -y --no-install-recommends kiwix-tools
binary=/usr/bin/kiwix-serve
manage=/usr/bin/kiwix-manage
[[ -x "$binary" && -x "$manage" ]] || { echo 'Kiwix tools are not ready yet. Stop here and report this message.' >&2; exit 1; }
[[ -f /mnt/data/kiwix/library.xml ]] || { echo 'Kiwix library manifest is missing.' >&2; exit 1; }
if [[ -f /etc/systemd/system/maha-kiwix.service ]]; then
    backup=$(mktemp -d /mnt/data/backups/kiwix-service-$(date +%Y%m%d-%H%M%S)-XXXXXX)
    cp -a /etc/systemd/system/maha-kiwix.service "$backup/"
fi
cat > /etc/systemd/system/maha-kiwix.service <<'UNIT'
[Unit]
Description=MAHASARAKHAM offline Kiwix library
After=network.target
RequiresMountsFor=/mnt/data/kiwix

[Service]
Type=simple
User=vhenderson
Group=vhenderson
ExecStart=/usr/bin/kiwix-serve --address=127.0.0.1 --port=8091 --urlRootLocation=kiwix --library --monitorLibrary --blockexternal /mnt/data/kiwix/library.xml
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now maha-kiwix.service
systemctl is-active --quiet maha-kiwix.service
ready=false
for attempt in {1..20}; do
    if curl --fail --silent http://127.0.0.1:8091/kiwix/ >/dev/null; then ready=true; break; fi
    sleep 1
done
[[ "$ready" == true ]] || { echo 'Kiwix did not become ready. Check: sudo journalctl -u maha-kiwix -n 30' >&2; exit 1; }
bash "$stage/install-library-site.sh"
curl --fail --silent --show-error http://192.168.1.64/kiwix/ -o /dev/null
printf '\nKiwix is connected: http://192.168.1.64/kiwix/\n'
printf 'Use Knowledge > Open Kiwix library in the MAHA portal.\n'
printf 'Verified archives appear progressively during the Windows-to-Ubuntu transfer.\n'
printf 'Service: maha-kiwix.service (starts automatically after reboot).\n'
