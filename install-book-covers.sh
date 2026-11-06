#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
base=/mnt/data/projects/maha-library/cover-update
live=$(readlink -f /srv/www/maha-library/current)/dist
backup=$(mktemp -d /mnt/data/backups/book-covers-XXXXXXXX)
cp -a "$live/index.html" "$live/catalog.json" "$backup/"
if [[ -d "$live/covers" ]]; then cp -a "$live/covers" "$backup/"; fi
python3 - "$base" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);books=json.loads((p/'catalog.json').read_text())
assert len(books)==119
for b in books:
 assert (p/b['cover']).is_file(),b['title']
print('Verified 119 cover images.')
PY
install -d -m 755 "$live/covers"
install -m 644 "$base"/covers/*.jpg "$live/covers/"
install -m 644 "$base/catalog.json" "$live/catalog.json"
install -m 644 "$base/index.html" "$live/index.html"
curl -fsS http://192.168.1.64/catalog.json >/dev/null
printf 'Book covers installed. Backup: %s\nRefresh http://192.168.1.64/\n' "$backup"
