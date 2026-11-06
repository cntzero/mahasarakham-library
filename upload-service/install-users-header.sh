#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
backup=$(mktemp -d /mnt/data/backups/library-users-header-XXXXXXXX)
cp -a "$live/access.html" "$backup/access.html"
trap 'cp -a "$backup/access.html" "$live/access.html"' ERR
install -m 644 /mnt/data/projects/maha-library/upload-service/site/access.html "$live/access.html"
trap - ERR
echo "Users shared header installed. Backup: $backup"
