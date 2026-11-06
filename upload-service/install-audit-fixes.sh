#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || { echo 'Unexpected website location.'; exit 1; }
python3 "$stage/test_local_https.py"
mapfile -t files < <(find "$stage/site" -maxdepth 1 -type f \( -name '*.html' -o -name '*.css' -o -name '*.js' \) -printf '%f\n' | sort)
backup=$(mktemp -d /mnt/data/backups/library-audit-fixes-XXXXXXXX)
chmod 700 "$backup"
for file in "${files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/$file"; done
rollback(){ trap - ERR; for file in "${files[@]}"; do if [[ -f "$backup/$file" ]]; then cp -a "$backup/$file" "$live/$file"; else rm -f "$live/$file"; fi; done; echo "Installation failed; website restored from $backup" >&2; exit 1; }
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/site/$file" "$live/$file"; done
nginx -t
curl --cacert /mnt/data/projects/maha-library/maha-local-root-ca.crt -fsS https://192.168.1.64/login.html | python3 -c 'import sys; s=sys.stdin.read(); assert "href=\"/upload.css\"" in s and "src=\"/login.js" in s'
trap - ERR
printf 'MAHA audit fixes installed. Original books, archives, accounts and network settings are unchanged.\nBackup: %s\nWebsite: https://192.168.1.64/\n' "$backup"
