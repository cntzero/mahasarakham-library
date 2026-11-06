#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
export PYTHONPATH=/mnt/data/projects/maha-library/music-vendor
python3 "$stage/test_artwork_cooldown.py"
python3 "$stage/test_music_art.py"
backup=$(mktemp -d /mnt/data/backups/library-artwork-retry-XXXXXXXX)
chmod 700 "$backup"
cp -a /opt/maha-library-api/music_art_worker.py "$backup/"
systemctl stop maha-music-artwork.service
rollback(){ trap - ERR; cp -a "$backup/music_art_worker.py" /opt/maha-library-api/music_art_worker.py; systemctl start maha-music-artwork.service; echo "Worker restored. Backup: $backup" >&2; exit 1; }
trap rollback ERR
python3 - "$backup/catalog.sqlite" <<'PY'
import sqlite3,sys
with sqlite3.connect('/mnt/data/survival-library/music/catalog.sqlite') as db,sqlite3.connect(sys.argv[1]) as backup:
 db.backup(backup)
 count=db.execute("UPDATE artwork_jobs SET state='queued',attempts=0,nextAttempt=0,message='Queued after artwork connection retry fix.',updated=0 WHERE state IN ('waiting','fallback','error') AND (lastError LIKE 'Artwork service connection unavailable%' OR lastError LIKE 'HTTP 503%' OR lastError LIKE 'HTTP 502%' OR lastError LIKE 'HTTP 504%' OR lastError LIKE 'HTTP 429%')").rowcount
 print('Connection-failed artwork jobs requeued:',count)
PY
install -m 644 "$stage/music_art_worker.py" /opt/maha-library-api/music_art_worker.py
systemctl start maha-music-artwork.service
systemctl is-active --quiet maha-music-artwork.service
trap - ERR
echo 'Artwork cooldown fix installed; affected jobs will retry automatically.'
echo "Backup: $backup"
