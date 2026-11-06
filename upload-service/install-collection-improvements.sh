#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
config=$(readlink -f /etc/nginx/sites-enabled/maha-library)
ca=/mnt/data/projects/maha-library/maha-local-root-ca.crt
python=/opt/maha-library-api/venv/bin/python
[[ -x "$python" ]] || python=python3
"$python" "$stage/test_collection_controls.py"
"$python" "$stage/test_access_workflow.py"
install -d -m 700 /srv/maha-library-api/backups
backup=$(mktemp -d /srv/maha-library-api/backups/collection-improvements-XXXXXXXX)
install -d "$backup/site" "$backup/api"
files=(index.html maha.css library-tools.js browse.js browse.css knowledge.html knowledge.js archive-editions.js knowledge.css archives.html archives.js archive-pages.json archive-navigation.js session.js session.css)
api_files=(server.py collection_controls.py)
cp -a "$config" "$backup/nginx.conf"
for file in "${files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/site/"; done
for file in "${api_files[@]}"; do [[ ! -f "/opt/maha-library-api/$file" ]] || cp -a "/opt/maha-library-api/$file" "$backup/api/"; done
python3 - "$backup/accounts.sqlite" <<'PY'
import sqlite3,sys,os
with sqlite3.connect('file:/srv/maha-library-api/accounts.sqlite?mode=ro',uri=True) as source:
    with sqlite3.connect(sys.argv[1]) as target:source.backup(target)
os.chmod(sys.argv[1],0o600)
PY
rollback() {
 trap - ERR
 for file in "${files[@]}"; do if [[ -f "$backup/site/$file" ]]; then cp -a "$backup/site/$file" "$live/$file"; else rm -f "$live/$file"; fi; done
 for file in "${api_files[@]}"; do if [[ -f "$backup/api/$file" ]]; then cp -a "$backup/api/$file" "/opt/maha-library-api/$file"; else rm -f "/opt/maha-library-api/$file"; fi; done
 cp -a "$backup/nginx.conf" "$config"
 systemctl restart maha-library-api.service || true
 nginx -t && systemctl reload nginx || true
 echo 'Update failed; previous pages and configuration restored.' >&2
 exit 1
}
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/site/$file" "$live/$file"; done
for file in "${api_files[@]}"; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file"; done
python3 - "$config" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
if 'location /archive/askaprepper/' not in s:
    block='''    # Preserved website mirror, protected by the existing library login.
    location /archive/askaprepper/ {
        alias /mnt/data/survival-library/web-articles/originals/askaprepper/;
        autoindex off;
        limit_except GET { deny all; }
        add_header Content-Security-Policy "sandbox allow-same-origin; default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; base-uri 'self'; form-action 'none'" always;
        add_header X-Content-Type-Options nosniff always;
        add_header Referrer-Policy no-referrer always;
        add_header X-Frame-Options SAMEORIGIN always;
    }
'''
    assert '    location / { ' in s
    s=s.replace('    location / { ',block+'    location / { ',1)
    p.write_text(s)
PY
nginx -t
systemctl restart maha-library-api.service
ready=false
for attempt in {1..20}; do
 if curl -fsS http://127.0.0.1:8123/api/library/health | python3 -c 'import json,sys;assert json.load(sys.stdin).get("collectionControls")' 2>/dev/null; then ready=true;break;fi
 sleep 1
done
[[ "$ready" == true ]]
systemctl reload nginx
curl --cacert "$ca" -fsS https://192.168.1.64/login.html >/dev/null
code=$(curl --cacert "$ca" -sS -o /dev/null -w '%{http_code}' https://192.168.1.64/api/library/kiwix)
[[ "$code" == 401 ]]
trap - ERR
echo 'Library improvements installed: https://192.168.1.64/'
echo 'Offline knowledge: https://192.168.1.64/knowledge.html'
echo 'Preserved websites: https://192.168.1.64/archives.html'
echo "Backup: $backup"
echo 'Press Ctrl+F5 to refresh. Original book and archive files are preserved.'
