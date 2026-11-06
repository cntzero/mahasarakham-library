#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
stage=/mnt/data/projects/maha-library
root=/srv/www/maha-library
[[ -f "$stage/dist/reader.js" && -f "$stage/maha-library.nginx.conf" ]] || { echo 'Site staging files are missing.' >&2; exit 1; }
nginx -t
backup=$(mktemp -d /mnt/data/backups/library-web-deploy-$(date +%Y%m%d-%H%M%S)-XXXXXX)
chmod 700 "$backup"
cp -a /etc/nginx "$backup/nginx"
mkdir -p "$root/releases"
release=$(mktemp -d "$root/releases/site-$(date +%Y%m%d-%H%M%S)-XXXXXX")
cp -a "$stage/dist" "$release/dist"
chown -R root:root "$release"
find "$release" -type d -exec chmod 755 {} +
find "$release" -type f -exec chmod 644 {} +
previous=''
if [[ -e "$root/current" && ! -L "$root/current" ]]; then echo 'Current site path is not a symlink; stopped for inspection.' >&2; exit 1; fi
if [[ -L "$root/current" ]]; then previous=$(readlink "$root/current"); fi
default_removed=false
prior_site=false
if [[ -e /etc/nginx/sites-enabled/maha-library && ! -L /etc/nginx/sites-enabled/maha-library ]]; then echo 'Unexpected enabled-site file; stopped.' >&2; exit 1; fi
[[ -e /etc/nginx/sites-available/maha-library ]] && prior_site=true
rollback() {
    rc=$?
    if [[ "$rc" -ne 0 ]]; then
        echo 'Deployment failed; restoring previous Nginx configuration.' >&2
        if [[ "$prior_site" == true ]]; then cp -a "$backup/nginx/sites-available/maha-library" /etc/nginx/sites-available/maha-library;
        else rm -f /etc/nginx/sites-enabled/maha-library /etc/nginx/sites-available/maha-library; fi
        if [[ "$default_removed" == true ]]; then cp -a "$backup/nginx/sites-enabled/default" /etc/nginx/sites-enabled/default; fi
        if [[ -n "$previous" ]]; then ln -sfn "$previous" "$root/current";
        else rm -f "$root/current"; fi
        nginx -t && systemctl restart nginx || true
    fi
}
trap rollback EXIT
if [[ -L /etc/nginx/sites-enabled/default ]]; then
    rm /etc/nginx/sites-enabled/default
    default_removed=true
elif [[ -e /etc/nginx/sites-enabled/default ]]; then
    echo 'Default site is not a symlink; stopped for inspection.' >&2
    exit 1
fi
install -m 644 "$stage/maha-library.nginx.conf" /etc/nginx/sites-available/maha-library
ln -sfn /etc/nginx/sites-available/maha-library /etc/nginx/sites-enabled/maha-library
ln -sfn "$release" "$root/current"
nginx -t
# The earlier baseline changed wildcard listeners to a specific LAN address.
# Reload can keep old sockets and fail to bind the more specific address while
# returning success to systemctl. Restart releases those original sockets.
systemctl restart nginx
systemctl is-active --quiet nginx
curl --fail --silent --show-error http://192.168.1.64/catalog.json > "$backup/catalog-response.json"
python3 - "$backup/catalog-response.json" <<'PY'
import json,sys
c=json.load(open(sys.argv[1]));assert len(c)==119
assert all(b.get('sources') for b in c)
print('Catalog check passed: 119 entries')
PY
curl --fail --silent --show-error --head http://192.168.1.64/vendor/epub.min.js >/dev/null
trap - EXIT
printf '\nLibrary website installed: http://192.168.1.64/\n'
printf 'Configuration backup: %s\nRelease: %s\n' "$backup" "$release"
printf 'Open WebUI remains on port 8080. Kiwix archives are not connected yet.\n'
