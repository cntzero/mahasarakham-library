#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
source=/mnt/data/projects/maha-library/upload-service/site/index.html
backup=$(mktemp -d /mnt/data/backups/library-home-links-XXXXXXXX)
cp -a "$live/index.html" "$backup/index.html"
trap 'cp -a "$backup/index.html" "$live/index.html"' ERR
install -m 644 "$source" "$live/index.html"
trap - ERR
echo "Home-page link interception fixed. Backup: $backup"
