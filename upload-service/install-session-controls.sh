#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
ca=/mnt/data/projects/maha-library/maha-local-root-ca.crt
files=(session.js session.css index.html add-books.html access.html access-procedure.html)
for file in "${files[@]}"; do test -f "$stage/$file"; done
install -d -m 700 /srv/maha-library-api/backups
backup=$(mktemp -d /srv/maha-library-api/backups/session-controls-XXXXXXXX)
for file in "${files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/"; done
rollback() {
  trap - ERR
  for file in "${files[@]}"; do
    if [[ -f "$backup/$file" ]]; then cp -a "$backup/$file" "$live/$file"; else rm -f "$live/$file"; fi
  done
  echo 'Connection check failed; previous pages restored.' >&2
  exit 1
}
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$live/$file"; done
curl --cacert "$ca" -fsS https://192.168.1.64/login.html >/dev/null
curl --cacert "$ca" -fsS https://192.168.1.64/api/library/session | python3 -c 'import json,sys; assert json.load(sys.stdin).get("enabled") is True'
code=$(curl --cacert "$ca" -sS -o /dev/null -w '%{http_code}' https://192.168.1.64/api/library/books)
[[ "$code" == 401 ]]
trap - ERR
echo 'Account and Log out controls installed. Refresh the library with Ctrl+F5.'
echo "Backup: $backup"
