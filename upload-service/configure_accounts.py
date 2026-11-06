"""Add local HTTPS/auth without replacing existing VPN/LAN access rules."""
from pathlib import Path
import sys

def configure(text):
    if '# BEGIN MAHA LOCAL ACCOUNTS' in text:return text
    if '# BEGIN MAHA ACCOUNTS' in text:raise ValueError('Older account configuration found; review before replacing.')
    if '    server_name _;' not in text or '    location /api/library/ {' not in text:
        raise ValueError('Expected library configuration not found. No changes made.')
    text=text.replace('    server_name _;','''    listen 192.168.1.64:443 ssl;
    ssl_certificate /etc/maha-library/pki/server.crt;
    ssl_certificate_key /etc/maha-library/pki/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    server_name _;
    # BEGIN MAHA LOCAL ACCOUNTS
    if ($scheme = http) { return 302 https://192.168.1.64$request_uri; }
    auth_request /_maha_auth;
    error_page 401 = /login.html;
    location = /_maha_auth {
        internal;
        auth_request off;
        proxy_pass http://127.0.0.1:8123/api/library/auth-check;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header Cookie $http_cookie;
    }
    location = /login.html { auth_request off; }
    location = /login.js { auth_request off; }
    location = /upload.css { auth_request off; }
    # END MAHA LOCAL ACCOUNTS''',1)
    start=text.index('    location /api/library/ {');end=text.index('}',start)
    block=text[start:end]
    extra=''
    if 'auth_request off;' not in block:extra+='\n        auth_request off;'
    if 'proxy_set_header X-Real-IP ' not in block:extra+='\n        proxy_set_header X-Real-IP $remote_addr;'
    return text[:start]+text[start:].replace('    location /api/library/ {','    location /api/library/ {'+extra,1)

if __name__=='__main__':
    path=Path(sys.argv[1]);path.write_text(configure(path.read_text()))
