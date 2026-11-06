#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
# Install the staged application/UI first if this machine has an older version.
if ! cmp -s "$stage/server.py" /opt/maha-library-api/server.py || ! cmp -s "$stage/site/index.html" /srv/www/maha-library/current/dist/index.html || [[ ! -f /srv/www/maha-library/current/dist/login.html ]]; then
    bash "$stage/install-uploads.sh"
fi
systemctl is-active --quiet maha-library-api.service
python3 "$stage/test_accounts_classification.py"
bash "$stage/setup-local-tls.sh"
install -d -m 700 -o vhenderson -g vhenderson /srv/maha-library-api
sudo -u vhenderson env MAHA_AUTH_DB=/srv/maha-library-api/accounts.sqlite python3 /opt/maha-library-api/accounts.py
backup=$(mktemp -d /mnt/data/backups/library-accounts-XXXXXXXX)
config=$(readlink -f /etc/nginx/sites-enabled/maha-library)
cp -a "$config" "$backup/nginx.conf"
install -d /etc/systemd/system/maha-library-api.service.d
dropin=/etc/systemd/system/maha-library-api.service.d/accounts.conf
[[ ! -f "$dropin" ]] || cp -a "$dropin" "$backup/accounts.conf"
rollback() {
    trap - ERR
    cp "$backup/nginx.conf" "$config"
    if [[ -f "$backup/accounts.conf" ]]; then cp "$backup/accounts.conf" "$dropin"; else rm -f "$dropin"; fi
    systemctl daemon-reload
    systemctl restart maha-library-api.service || true
    nginx -t && systemctl reload nginx || true
    echo "Activation failed; previous site configuration restored. Backup: $backup"
    exit 1
}
trap rollback ERR
cat >"$dropin" <<'UNIT'
[Service]
Environment=MAHA_REQUIRE_AUTH=1
Environment=MAHA_AUTH_DB=/srv/maha-library-api/accounts.sqlite
Environment=MAHA_PUBLIC_URL=https://192.168.1.64/
ReadWritePaths=/srv/maha-library-api
UNIT
python3 "$stage/configure_accounts.py" "$config"
nginx -t
systemctl daemon-reload
systemctl restart maha-library-api.service
systemctl reload nginx
connected=false
for attempt in {1..25}; do
    if curl --cacert /etc/maha-library/pki/ca.crt -fsS https://192.168.1.64/api/library/session 2>/dev/null | python3 -c 'import json,sys; assert json.load(sys.stdin).get("enabled")' 2>/dev/null; then connected=true; break; fi
    sleep 1
done
[[ "$connected" == true ]] || rollback
python3 "$stage/verify_protected_routes.py"
trap - ERR
printf '\nLibrary accounts and HTTPS enabled: https://192.168.1.64/\nYour router WireGuard settings and existing VPN allowance are preserved.\nPublic trust certificate: /mnt/data/projects/maha-library/maha-local-root-ca.crt\nTrust this certificate on your devices before opening the HTTPS site; do not bypass certificate warnings.\nBackup: %s\n' "$backup"
openssl x509 -in /etc/maha-library/pki/ca.crt -noout -sha256 -fingerprint
