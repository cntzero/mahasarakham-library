#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
api=/opt/maha-library-api
live=$(readlink -f /srv/www/maha-library/current)/dist
config=$(readlink -f /etc/nginx/sites-enabled/maha-library)
ca=/mnt/data/projects/maha-library/maha-local-root-ca.crt
curl --cacert "$ca" -fsS https://192.168.1.64/api/library/session | python3 -c 'import json,sys; assert json.load(sys.stdin).get("enabled"), "Enable library accounts first."'
python3 "$stage/test_access_workflow.py"
python3 "$stage/test_accounts_classification.py"
install -d -m 700 /srv/maha-library-api/backups
backup=$(mktemp -d /srv/maha-library-api/backups/access-workflow-XXXXXXXX)
install -d "$backup/api" "$backup/site"
cp -a "$config" "$backup/nginx.conf"
api_files=(server.py accounts.py access_workflow.py collection_controls.py)
site_files=(session.js session.css users.html access.html access.js access.css access-procedure.html)
for file in "${api_files[@]}"; do [[ ! -f "$api/$file" ]] || cp -a "$api/$file" "$backup/api/"; done
for file in "${site_files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/site/"; done
python3 - "$backup/accounts.sqlite" <<'PY'
import sqlite3,sys,os
with sqlite3.connect('file:/srv/maha-library-api/accounts.sqlite?mode=ro',uri=True) as source:
    with sqlite3.connect(sys.argv[1]) as destination:source.backup(destination)
os.chmod(sys.argv[1],0o600)
PY
rollback() {
    trap - ERR
    for file in "${api_files[@]}"; do
        if [[ -f "$backup/api/$file" ]]; then cp -a "$backup/api/$file" "$api/$file"; else rm -f "$api/$file"; fi
    done
    for file in "${site_files[@]}"; do
        if [[ -f "$backup/site/$file" ]]; then cp -a "$backup/site/$file" "$live/$file"; else rm -f "$live/$file"; fi
    done
    cp "$backup/nginx.conf" "$config"
    systemctl restart maha-library-api.service || true
    nginx -t && systemctl reload nginx || true
    echo "Workflow update failed; previous application/configuration restored. Backup: $backup"
    echo 'Additive database tables were retained; existing accounts were not replaced.'
    exit 1
}
trap rollback ERR
for file in "${api_files[@]}"; do install -m 644 "$stage/$file" "$api/$file"; done
for file in "${site_files[@]}"; do install -m 644 "$stage/site/$file" "$live/$file"; done
python3 - "$config" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();anchor='    allow 192.168.1.0/24;'
if 'allow 10.5.5.0/24;' not in s:
    if anchor not in s:raise SystemExit('Expected LAN access rule missing; refusing to guess.')
    s=s.replace(anchor,anchor+'\n    allow 10.5.5.0/24; # Devices authenticated by the router WireGuard server',1)
    p.write_text(s)
PY
nginx -t
systemctl restart maha-library-api.service
ready=false
for attempt in {1..25}; do
    if curl -fsS http://127.0.0.1:8123/api/library/health 2>/dev/null | python3 -c 'import json,sys; assert json.load(sys.stdin).get("accessWorkflow")' 2>/dev/null; then ready=true; break; fi
    sleep 1
done
[[ "$ready" == true ]] || rollback
systemctl reload nginx
python3 "$stage/verify_protected_routes.py"
trap - ERR
printf '\nPeople & access workflow installed.\nSign in as a Super user, then open Users: https://192.168.1.64/access.html\nPrintable procedure: https://192.168.1.64/access-procedure.html\nProtected backup: %s\nRouter profiles still require manual creation/removal; the UI saves the checklist.\n' "$backup"
