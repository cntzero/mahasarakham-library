#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
files=(archives.html archives.js archives.css)
backup=$(mktemp -d /mnt/data/backups/library-preserved-layout-XXXXXXXX)
for file in "${files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/"; done
rollback(){ trap - ERR; for file in "${files[@]}"; do if [[ -f "$backup/$file" ]]; then cp -a "$backup/$file" "$live/$file"; else rm -f "$live/$file"; fi; done; exit 1; }
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$live/$file"; done
trap - ERR
echo "Preserved web layout installed. Captured files are unchanged. Backup: $backup"
