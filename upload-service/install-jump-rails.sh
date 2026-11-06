#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.';exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
files=(jump-rail.js jump-rail.css catalog-state.js music.js knowledge.js archives.js index.html music.html knowledge.html archives.html)
for file in "${files[@]}";do test -s "$stage/$file";done
backup=$(mktemp -d /mnt/data/backups/library-jump-rails-XXXXXXXX)
chmod 700 "$backup"
for file in "${files[@]}";do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/$file";done
rollback(){
 trap - ERR
 for file in "${files[@]}";do [[ ! -f "$backup/$file" ]] || cp -a "$backup/$file" "$live/$file";done
 echo "Previous pages restored; unused new shared assets retained. Backup: $backup" >&2;exit 1
}
trap rollback ERR
for file in "${files[@]}";do install -m 644 "$stage/$file" "$live/$file.new";mv -f "$live/$file.new" "$live/$file";cmp "$stage/$file" "$live/$file";done
trap - ERR
echo 'Smart jump rails installed for Music, Books, Knowledge and Preserved web. Labels follow each list’s sort order and filters.'
echo 'Refresh MAHA with Ctrl+F5. Longer lists show the jump control beside the shelf.'
echo "Backup: $backup"
