#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/mnt/data/projects/maha-library/upload-service
live=$(readlink -f /srv/www/maha-library/current)/dist
[[ "$live" == /srv/www/maha-library/releases/*/dist ]] || exit 1
backup=$(mktemp -d /mnt/data/backups/library-compilation-grouping-XXXXXXXX)
chmod 700 "$backup"
cp -a /opt/maha-library-api/music.py "$backup/music.py"
for file in music.js music.html; do cp -a "$live/$file" "$backup/$file"; done
rollback(){ trap - ERR; cp -a "$backup/music.py" /opt/maha-library-api/music.py; for file in music.js music.html; do cp -a "$backup/$file" "$live/$file"; done; systemctl restart maha-library-api.service || true; echo "Previous files restored: $backup" >&2; exit 1; }
trap rollback ERR
install -m 644 "$stage/music.py" /opt/maha-library-api/music.py
for file in music.js music.html; do install -m 644 "$stage/site/$file" "$live/$file"; done
# Initialise the additive audio fingerprint column before restarting readers.
PYTHONPATH=/opt/maha-library-api/music-vendor python3 -c "import sys;sys.path.insert(0,'/opt/maha-library-api');import music;music.connect().close()"
systemctl restart maha-library-api.service
for file in index_audio_duplicates.py follow_audio_duplicates.py; do install -m 644 "$stage/$file" "/opt/maha-library-api/$file"; done
if ! systemctl is-active --quiet maha-audio-duplicate-index.service; then
 systemctl reset-failed maha-audio-duplicate-index.service 2>/dev/null || true
 systemd-run --collect --unit=maha-audio-duplicate-index --uid=vhenderson --setenv=PYTHONPATH=/opt/maha-library-api/music-vendor /usr/bin/python3 -u /opt/maha-library-api/follow_audio_duplicates.py
fi
trap - ERR
echo 'Artist normalization and MP3 audio deduplication installed. Existing recordings are being indexed in the background; no files are deleted. Refresh Music with Ctrl+F5.'
echo "Backup: $backup"
