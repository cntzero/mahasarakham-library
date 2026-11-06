"""Check certificate parameters and Nginx syntax without touching live settings."""
import subprocess,tempfile,re
from pathlib import Path
from configure_accounts import configure

def run(args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
with tempfile.TemporaryDirectory(prefix='maha-https-check-') as td:
    root=Path(td);ca=root/'ca.crt';key=root/'ca.key';cert=root/'server.crt';serverkey=root/'server.key';csr=root/'server.csr';ext=root/'server.ext'
    run(['openssl','req','-x509','-newkey','rsa:3072','-sha256','-nodes','-days','2','-keyout',str(key),'-out',str(ca),'-subj','/CN=MAHA Test Root','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign'])
    run(['openssl','req','-new','-newkey','rsa:2048','-nodes','-keyout',str(serverkey),'-out',str(csr),'-subj','/CN=192.168.1.64'])
    ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:192.168.1.64,DNS:MahaSarakhamUbuntu\n')
    run(['openssl','x509','-req','-in',str(csr),'-CA',str(ca),'-CAkey',str(key),'-CAcreateserial','-out',str(cert),'-days','1','-sha256','-extfile',str(ext)])
    run(['openssl','verify','-CAfile',str(ca),'-verify_ip','192.168.1.64',str(cert)])
    original=Path('/etc/nginx/sites-enabled/maha-library').read_text();configured=configure(original)
    assert re.findall(r'\ballow\s+[^;]+;',original)==re.findall(r'\ballow\s+[^;]+;',configured),'Working LAN/VPN allowances must be preserved'
    assert configure(configured)==configured,'Configuration should be idempotent'
    # Independent installation fixtures, not another directive injected into an
    # already-enabled live configuration. Both supported upload versions migrate.
    baseline='''server {
    listen 192.168.1.64:80;
    server_name _;
    allow 192.168.1.0/24;
    allow 10.5.5.2;
    deny all;
    location /api/library/ {
        proxy_pass http://127.0.0.1:8123;
    }
}'''
    for fixture in (baseline,baseline.replace('    location /api/library/ {','    location /api/library/ {\n        auth_request off;\n        proxy_set_header X-Real-IP $remote_addr;')):
        migrated=configure(fixture)
        block=migrated.split('    location /api/library/ {',1)[1].split('}',1)[0]
        assert block.count('auth_request off;')==1,'Avoid duplicate directives on upload installs'
        assert block.count('proxy_set_header X-Real-IP ')==1
        assert configure(migrated)==migrated,'Enabled fixture must be idempotent'
    assert '8089' not in configured and 'tailscale' not in configured.lower()
    configured=configured.replace('192.168.1.64:80','127.0.0.1:18080').replace('192.168.1.64:443','127.0.0.1:18443').replace('/etc/maha-library/pki/server.crt',str(cert)).replace('/etc/maha-library/pki/server.key',str(serverkey))
    site=root/'site.conf';site.write_text(configured);conf=root/'nginx.conf'
    conf.write_text(f'pid {root}/nginx.pid; error_log stderr; events {{}} http {{ access_log off; client_body_temp_path {root}/body; proxy_temp_path {root}/proxy; fastcgi_temp_path {root}/fcgi; uwsgi_temp_path {root}/uwsgi; scgi_temp_path {root}/scgi; include {site}; }}')
    run(['nginx','-t','-c',str(conf),'-p',td])
print('Private certificate/IP verification, WireGuard rule preservation, idempotence, and HTTPS Nginx syntax: passed')
