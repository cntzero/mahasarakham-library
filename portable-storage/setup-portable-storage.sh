#!/usr/bin/env bash
# Establish stable service paths without moving any data or formatting disks.
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
stage=$(cd -- "$(dirname -- "$0")" && pwd)
[[ -d /mnt/data/survival-library && -f /mnt/data/kiwix/library.xml ]] || { echo 'Expected existing data directories not found.' >&2; exit 1; }
[[ -f "$stage/maha-library.portable.conf" ]] || { echo 'Portable Nginx configuration missing.' >&2; exit 1; }
python3 - <<'PY'
from pathlib import Path
import json
p=Path('/mnt/data/survival-library/web-articles/preservation/verification.json')
assert p.exists(), 'Website mirror copy is not verified yet; wait for completion.'
m=json.loads(p.read_text())
assert m.get('state')=='complete' and not m.get('failures'), 'Website mirror verification is not complete.'
PY
backup=$(mktemp -d /mnt/data/backups/portable-storage-$(date +%Y%m%d-%H%M%S)-XXXXXX)
chmod 700 "$backup"
cp -a /etc/nginx "$backup/nginx"
for name in library kiwix; do
    unit=$(systemd-escape --path --suffix=mount "/srv/maha-data/$name")
    [[ ! -f "/etc/systemd/system/$unit" ]] || cp -a "/etc/systemd/system/$unit" "$backup/"
done
[[ ! -d /etc/systemd/system/maha-kiwix.service.d ]] || cp -a /etc/systemd/system/maha-kiwix.service.d "$backup/"
for name in library kiwix; do
    target="/srv/maha-data/$name"
    if [[ -L "$target" ]]; then echo "Unexpected symlink: $target" >&2; exit 1; fi
    if [[ -d "$target" ]] && ! mountpoint -q "$target" && [[ -n "$(ls -A "$target")" ]]; then
        echo "Nonempty unmounted target: $target. Stopped to avoid hiding files." >&2; exit 1
    fi
done
mkdir -p /srv/maha-data/library /srv/maha-data/kiwix
for name in library kiwix; do
    source=/mnt/data/kiwix
    [[ "$name" != library ]] || source=/mnt/data/survival-library
    unit=$(systemd-escape --path --suffix=mount "/srv/maha-data/$name")
    if [[ -f "/etc/systemd/system/$unit" ]]; then
        grep -qx "What=$source" "/etc/systemd/system/$unit" || { echo "Existing $unit differs; inspect before changing." >&2; exit 1; }
    fi
    cat > "/etc/systemd/system/$unit" <<EOF
[Unit]
Description=MAHA stable $name storage path
RequiresMountsFor=$source

[Mount]
What=$source
Where=/srv/maha-data/$name
Type=none
Options=bind

[Install]
WantedBy=multi-user.target
EOF
done
systemctl daemon-reload
systemctl enable --now "$(systemd-escape --path --suffix=mount /srv/maha-data/library)" "$(systemd-escape --path --suffix=mount /srv/maha-data/kiwix)"
[[ "$(stat -c '%d:%i' /mnt/data/survival-library)" == "$(stat -c '%d:%i' /srv/maha-data/library)" ]]
[[ "$(stat -c '%d:%i' /mnt/data/kiwix)" == "$(stat -c '%d:%i' /srv/maha-data/kiwix)" ]]
install -m 644 "$stage/maha-library.portable.conf" /etc/nginx/sites-available/maha-library
if ! nginx -t; then cp -a "$backup/nginx/sites-available/maha-library" /etc/nginx/sites-available/maha-library; exit 1; fi
mkdir -p /etc/systemd/system/maha-kiwix.service.d
cat > /etc/systemd/system/maha-kiwix.service.d/storage.conf <<'EOF'
[Unit]
RequiresMountsFor=
RequiresMountsFor=/srv/maha-data/kiwix

[Service]
ExecStart=
ExecStart=/usr/bin/kiwix-serve --address=127.0.0.1 --port=8091 --urlRootLocation=kiwix --library --monitorLibrary --blockexternal /srv/maha-data/kiwix/library.xml
EOF
systemctl daemon-reload
systemctl restart maha-kiwix
systemctl reload nginx
curl --fail --silent --show-error http://192.168.1.64/catalog.json >/dev/null
findmnt /srv/maha-data/library
findmnt /srv/maha-data/kiwix
printf '\nStable storage paths activated. No data moved.\nBackup: %s\n' "$backup"
