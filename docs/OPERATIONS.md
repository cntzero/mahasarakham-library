# Operations, backup, restore and troubleshooting

## Daily diagnostics

```bash
systemctl status maha-library-api maha-music-identification maha-music-artwork --no-pager
journalctl -u maha-library-api -n 80 --no-pager
journalctl -u maha-music-identification -n 80 --no-pager
df -h /mnt/data
curl --fail http://127.0.0.1:8123/api/library/health
```

Never paste database contents, tokens or private fingerprints into public logs/issues. Review disk capacity before imports/conversions. Artwork/recognition are optional workers; failures should not prevent local playback.

## Updates on the existing server

1. Commit/review source changes. Keep `dist/` and `upload-service/site/` synchronized.
2. Run checks in [DEVELOPMENT.md](DEVELOPMENT.md).
3. Back up the active static release, `/opt/maha-library-api`, affected Nginx/systemd files and runtime databases.
4. Create a new release directory; copy the complete frontend into its `dist/`. Copy the current private `catalog.json` / `archive-pages.json` into it. Do not replace real manifests with empty ones.
5. Install changed Python modules preserving ownership/modes. Atomically switch the `current` symlink to the new release. Avoid changing production data paths.
6. Restart only services whose Python code/config changed; reload Nginx only if its config changed, after `nginx -t`. A frontend-only update needs no backend restart.
7. Verify health, login, protected routes, reading/playback and the changed workflow; refresh browser caches. Keep the previous release and matching backend backup for rollback.

Older per-change installers are retained, but their guards/hashes/layout assumptions may be obsolete. Do not replay them all. The new `deploy/install-source.sh` intentionally refuses an existing deployment.

## Consistent backups

Git is a software backup, not a library backup. Use a separate encrypted backup destination with enough capacity. For a simple consistent offline backup, schedule a maintenance window, stop the API/artwork/identification workers and any standalone import/tagging process, then copy:

- All `/mnt/data/survival-library` collections, including originals, managed MP3s, metadata, SQLite databases and job/settings files.
- `/srv/maha-library-api`, `/etc/maha-library`, and relevant `/etc/nginx` / systemd files.
- `/mnt/data/kiwix`, private catalog manifests and `asset-map.json`.
- Windows receiver progress DB and any import reports needed for audit/resume.

Use `rsync -a` to a dedicated backup filesystem (do not use `--delete` unless you explicitly intend mirror deletion). Restart services afterward and verify health. For online SQLite backups use SQLite's backup API/`.backup`; copying only a live `.sqlite` file can miss WAL changes. Test a restore on a separate host. Keep media and database snapshots from the same point in time.

## Restore

Prepare software using SERVER-SETUP, stop writers, restore the matching data directories/databases/configuration, fix ownership to the configured service user and retain root-only key/token permissions. Restore private static manifests into the release and verify every referenced media path. Do not generate a new root CA if you restored the original CA and want existing clients to retain trust. Start the API first, then workers/Nginx; test login, permissions, uploads, playback and metadata before allowing imports.

## Common symptoms

| Symptom | Check |
|---|---|
| 502 / API unavailable | API service logs, writable directories, missing Pillow/Mutagen, mounted data disk |
| Empty Books after restore | Private baseline catalog and imported-books catalog both restored; active release paths |
| Cover/media 404 | Nginx aliases, filesystem permissions, matching media/catalog backup |
| HTTPS warning | Correct IP/hostname SAN, validity period, client root-CA trust; do not bypass |
| Recognition unavailable | Worker active, `fpcalc`, application key, DNS/outbound HTTPS and provider outage/rate limit |
| More than 1,000 unknown tracks | Use a track's Identify action; do not apply one album's metadata to unrelated tracks |
| Imports repeatedly skipped | SHA-256 duplicate handling/progress DB; originals remain separate |
| AI suggestions absent | Optional local Ollama/model configuration and tagging worker, not a playback requirement |
| Player stops | Full refresh/tab close restarts the audio owner; remain inside the same MAHA shell tab |

Permanent deletion removes managed media and artwork; source-drive originals remain separate. Keep tested backups before destructive bulk actions.
