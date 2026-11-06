#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
files=(index.html browse.js music.html music.js music.css knowledge.html knowledge-discoveries.js discovery.css discovery.js)
for file in "${files[@]}"; do test -s "$stage/$file"; done
backup=$(mktemp -d /mnt/data/backups/library-shared-discovery-XXXXXXXX)
chmod 700 "$backup"
for file in "${files[@]}"; do [[ ! -f "$live/$file" ]] || cp -a "$live/$file" "$backup/$file"; done
rollback(){ trap - ERR; for file in "${files[@]}"; do if [[ -f "$backup/$file" ]]; then cp -a "$backup/$file" "$live/$file"; else rm -f "$live/$file"; fi; done; echo "Update failed; previous pages restored. Backup: $backup" >&2; exit 1; }
trap rollback ERR
# Shared assets are installed before pages that reference them.
for file in discovery.css discovery.js; do install -m 644 "$stage/$file" "$live/$file"; done
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$live/$file"; cmp "$stage/$file" "$live/$file"; done
python3 - "$live" <<'PY'
import sys
from pathlib import Path
root=Path(sys.argv[1])
for name in ('index.html','music.html','knowledge.html'):
 text=(root/name).read_text()
 assert 'discovery.css?v=shared-2' in text and 'discovery.js?v=shared-2' in text
 assert 'class="hero discovery-hero"' in text and 'class="landscape discovery-landscape"' in text
print('All three installed pages reference the same discovery layout and controls.')
PY
trap - ERR
echo 'Shared Daily Discoveries installed for Books, Music and Knowledge.'
echo "Backup: $backup"
