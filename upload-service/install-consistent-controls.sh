#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service/site
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
files=(index.html knowledge.html book-dates.js catalog-controls.css tag-filter.js tag-filter.css knowledge.js knowledge.css)
backup=$(mktemp -d /mnt/data/backups/library-consistent-controls-XXXXXXXX)
for file in "${files[@]}"; do if [[ -f "$live/$file" ]]; then cp -a "$live/$file" "$backup/"; fi; done
rollback(){ trap - ERR; for file in "${files[@]}"; do if [[ -f "$backup/$file" ]]; then cp -a "$backup/$file" "$live/$file"; else rm -f "$live/$file"; fi; done; echo "Update failed; restored from $backup" >&2; exit 1; }
trap rollback ERR
for file in "${files[@]}"; do install -m 644 "$stage/$file" "$live/$file"; done
grep -q 'catalog-controls.css?v=2' "$live/index.html"
grep -q 'catalog-controls.css?v=2' "$live/knowledge.html"
python3 - "$live/knowledge.html" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
assert s.index('class="catalog-search"') < s.index('id="collection-chips"') < s.index('class="filters catalog-controls"'), 'Knowledge controls are in the wrong order'
PY
trap - ERR
echo "Books and Knowledge controls now share a consistent layout. Backup: $backup"
