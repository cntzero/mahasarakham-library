#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
base=/mnt/data/projects/maha-library
stage="$base/upload-service"
export DEBIAN_FRONTEND=noninteractive
if ! command -v ebook-convert >/dev/null || ! command -v pdftoppm >/dev/null || ! python3 -c 'import PIL' 2>/dev/null; then
    apt-get update
    apt-get install -y --no-install-recommends calibre python3-pil poppler-utils
fi
python3 "$stage/test_uploads.py" --require-mobi
python3 "$stage/test_accounts_classification.py"
python3 "$stage/test_access_workflow.py"
backup=$(mktemp -d /mnt/data/backups/library-uploads-XXXXXXXX)
config=$(readlink -f /etc/nginx/sites-enabled/maha-library)
live=$(readlink -f /srv/www/maha-library/current)/dist
cp -a "$config" "$backup/nginx.conf"
cp -a "$live/index.html" "$live/reader.js" "$live/reader.html" "$backup/"
for file in add-books.html upload.js upload.css; do [[ ! -e "$live/$file" ]] || cp -a "$live/$file" "$backup/"; done
[[ ! -f /etc/systemd/system/maha-library-api.service ]] || cp -a /etc/systemd/system/maha-library-api.service "$backup/"
install -d /opt/maha-library-api
install -m 644 "$stage/server.py" "$stage/classification.py" "$stage/accounts.py" "$stage/access_workflow.py" "$stage/collection_controls.py" /opt/maha-library-api/
install -d -o vhenderson -g vhenderson /mnt/data/survival-library/imported-books
cat >/etc/systemd/system/maha-library-api.service <<'UNIT'
[Unit]
Description=MAHA local book uploads and catalog
After=network.target
RequiresMountsFor=/mnt/data/survival-library/imported-books
[Service]
User=vhenderson
Group=vhenderson
ExecStart=/usr/bin/python3 /opt/maha-library-api/server.py
Restart=on-failure
Environment=QT_QPA_PLATFORM=offscreen
Environment=MAHA_IMPORT_ROOT=/mnt/data/survival-library/imported-books
UMask=0022
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
IPAddressDeny=any
IPAddressAllow=localhost
ReadWritePaths=/mnt/data/survival-library/imported-books
MemoryMax=2G
TasksMax=128
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now maha-library-api.service
systemctl restart maha-library-api.service
for attempt in {1..30}; do curl -fsS http://127.0.0.1:8123/api/library/health >/dev/null 2>&1 && break || sleep 1; done
curl -fsS http://127.0.0.1:8123/api/library/health >/dev/null
python3 - "$config" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
start='# BEGIN MAHA BOOK UPLOADS';end='# END MAHA BOOK UPLOADS'
if start in s:s=s[:s.index(start)]+s[s.index(end)+len(end):]
block='''    # BEGIN MAHA BOOK UPLOADS
    location /api/library/ {
        auth_request off;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 1024m;
        client_body_timeout 180s;
        proxy_pass http://127.0.0.1:8123;
        proxy_set_header Host $http_host;
        proxy_request_buffering off;
        proxy_read_timeout 900s;
        proxy_send_timeout 180s;
    }
    location /uploads/originals/ {
        alias /mnt/data/survival-library/imported-books/originals/;
        limit_except GET { deny all; }
        add_header Content-Security-Policy "sandbox; default-src 'none'" always;
    }
    location /uploads/readable/ {
        alias /mnt/data/survival-library/imported-books/readable/;
        limit_except GET { deny all; }
    }
    location /uploads/covers/ {
        alias /mnt/data/survival-library/imported-books/covers/;
        limit_except GET { deny all; }
    }
    # END MAHA BOOK UPLOADS
'''
pos=s.index('    location / {');s=s[:pos]+block+s[pos:];p.write_text(s)
PY
if ! nginx -t; then cp "$backup/nginx.conf" "$config"; exit 1; fi
systemctl reload nginx
for file in index.html maha.css reader.js reader.html add-books.html upload.js upload.css library-tools.js book-dates.js tag-filter.js tag-filter.css browse.js browse.css knowledge.html knowledge.js archive-editions.js knowledge.css archives.html archives.js archive-pages.json archive-navigation.js session.js session.css login.html login.js users.html users.js access.html access.js access.css access-procedure.html; do install -m 644 "$stage/site/$file" "$live/$file"; done
# Reload returns before replacement workers start accepting connections.
connected=false
health_url=http://192.168.1.64/api/library/health
curl_args=(-fsS)
if grep -q '# BEGIN MAHA LOCAL ACCOUNTS' "$config"; then
    health_url=https://192.168.1.64/api/library/health
    curl_args+=(--cacert /mnt/data/projects/maha-library/maha-local-root-ca.crt)
fi
for attempt in {1..20}; do
    if curl "${curl_args[@]}" "$health_url" 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ready") and d.get("mobi")' 2>/dev/null; then
        connected=true
        break
    fi
    sleep 1
done
if [[ "$connected" != true ]]; then
    cp "$backup/nginx.conf" "$config"; cp "$backup/index.html" "$backup/reader.js" "$backup/reader.html" "$live/"; nginx -t && systemctl reload nginx
    echo 'Connection check failed; website/config restored. Upload service files retained for diagnosis.'; exit 1
fi
printf '\nBulk book uploads ready: http://192.168.1.64/add-books.html\nBackup: %s\n' "$backup"
