#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || exit 1
umask 077
pki=/etc/maha-library/pki
install -d -m 700 "$pki"
if [[ ! -f "$pki/ca.key" ]]; then
    openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 3650 -keyout "$pki/ca.key" -out "$pki/ca.crt" -subj '/CN=MAHA Private Library Root CA' -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign'
fi
cat >"$pki/server.ext" <<'EXT'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:192.168.1.64,DNS:MahaSarakhamUbuntu
EXT
if [[ ! -f "$pki/server.key" ]]; then
    openssl req -new -newkey rsa:2048 -nodes -keyout "$pki/server.key" -out "$pki/server.csr" -subj '/CN=192.168.1.64'
fi
if [[ ! -f "$pki/server.crt" ]] || ! openssl x509 -checkend 2592000 -noout -in "$pki/server.crt"; then
    openssl x509 -req -in "$pki/server.csr" -CA "$pki/ca.crt" -CAkey "$pki/ca.key" -CAcreateserial -out "$pki/server.crt" -days 365 -sha256 -extfile "$pki/server.ext"
fi
install -m 644 "$pki/ca.crt" /mnt/data/projects/maha-library/maha-local-root-ca.crt
install -m 700 /mnt/data/projects/maha-library/upload-service/setup-local-tls.sh /usr/local/sbin/maha-renew-local-tls
cat >/etc/systemd/system/maha-local-tls-renew.service <<'UNIT'
[Unit]
Description=Renew MAHA private HTTPS certificate locally
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/maha-renew-local-tls
ExecStartPost=/usr/sbin/nginx -t
ExecStartPost=/bin/systemctl reload nginx
UNIT
cat >/etc/systemd/system/maha-local-tls-renew.timer <<'UNIT'
[Unit]
Description=Check MAHA private HTTPS certificate weekly
[Timer]
OnCalendar=weekly
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now maha-local-tls-renew.timer
openssl x509 -in "$pki/ca.crt" -noout -sha256 -fingerprint
