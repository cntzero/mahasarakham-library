# MAHA portable storage preparation

Prepared 3 November 2026. No drive formatted, no existing data moved, and no service paths changed by this preparation.

## Stable logical paths

| Service-facing path | Current backing directory | Proposed backing directory on new drive |
|---|---|---|
| `/srv/maha-data/library` | `/mnt/data/survival-library` | `/mnt/maha-storage/library` |
| `/srv/maha-data/kiwix` | `/mnt/data/kiwix` | `/mnt/maha-storage/kiwix` |

Two systemd bind mounts expose the data at the stable paths. The drive itself will be mounted by its verified UUID at `/mnt/maha-storage` after installation. Website URLs and catalog identities remain the same when the backing directories change. A separate media bind mount can be added when music/games storage exists; it is not needed yet.

`storage-layout.json` declares these mappings. `master-catalog.json` and CSV contain 1,920 entries: 119 books/manuals, 1,340 extracted articles, and 461 ZIM archives. Availability is a dated snapshot, not a live progress monitor. Source paths are relative to logical storage roots. Old title/format alternatives are retained.

## Original website preservation

Full Windows mirror inventory: 49,638 files / 4,049,773,879 bytes, including 7,583 HTML pages. The extended Windows path prefix was necessary to enumerate all files without read errors. Nothing was filtered out for relevance.

Copy process: build a complete preservation tar.gz under `web-articles/preservation`, compare its source-stream and server SHA-256, extract with safe path filtering into `web-articles/originals/askaprepper`, then verify every extracted file against the per-file source hashes. Until verification.json reports complete, do not claim a complete server mirror.

The additional `archives.html` browser uses server-relative links to original pages and images. Raw cookies/crawl logs/cache metadata remain preserved but are not published as browsing content. The Nginx archive route disables scripts and external resource requests while retaining locally captured images/styles; heavily scripted old pages may not behave like their live originals. The original 2021 capture itself was incomplete.

## Activation after the mirror is verified

The staged setup script creates bind mounts, backs up configuration, points Nginx aliases and Kiwix at the stable paths, and adds original-archive browsing. It stops before activation if preservation verification is missing or failed. It does not move files or initialize a disk. Root is required to install mounts and reload services.

Server command, only once the copy is verified:

```bash
sudo bash /mnt/data/projects/maha-library/portable-storage/setup-portable-storage.sh
```

Original paths remain usable while the present Kiwix transfer finishes. Keep all writers using one physical data set until migration is explicitly cut over.

## New-drive migration sequence

1. Finish/check active copies. Inventory the new physical disk, serial, capacity, existing partitions, data, and filesystem. Select the device explicitly before considering initialization. No formatting command is supplied here.
2. Agree filesystem and mount configuration; for a Linux server, evaluate ext4 and Samba access from Windows. Current `/mnt/data` is a fuseblk filesystem, so ownership/metadata behavior differs.
3. Mount the selected existing/new filesystem by UUID at `/mnt/maha-storage`. Confirm adequate free space and a healthy mount before copying.
4. Copy library and Kiwix to the proposed directories. Do not delete the old copies. Use a resumable transfer with source/destination checksum verification; review dry-run results before the copy. Initial copy can run while serving read-only material.
5. Stop transfer workers and other writers, stop Kiwix, make a final synchronization, and verify counts and checksums. Preserve Kiwix library.xml, registration records, manifests and website source/configuration.
6. Change only the two bind-mount backing sources and their mount dependencies. Restart mounts/services in dependency order; verify readers, PDFs, archived images, Kiwix search, and reboot behavior.
7. Review the Samba share backing Z: so the intended Windows paths continue working. Update diagnostic scripts/transfer destinations that still refer to old physical paths. Do not leave a writer feeding the old copy after cutover.
8. Keep the old disk data as a rollback copy until the new storage and recovery procedure pass checks. A second copy on a separate physical device is still needed for ongoing backup.

The live site release/source (`/srv/www/maha-library`, `/mnt/data/projects/maha-library`), Nginx/systemd configuration, and WebUI data (`/srv/ai/open-webui`) are application components outside these two data roots. Back them up separately. Ollama models need their own inventory/backup policy. Nothing here relocates the working WebUI database or model weights.
