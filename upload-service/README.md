# MAHA bulk book uploads

Staged, not yet enabled. Install on MAHA:

    sudo bash /mnt/data/projects/maha-library/upload-service/install-uploads.sh

The installer adds Ubuntu Calibre, Pillow and Poppler packages; runs isolated EPUB/PDF/MOBI checks; backs up the current website/configuration; enables a loopback-only Python service behind the existing LAN-only Nginx site; and adds the Add books page. It requires administrator access. The page supports files, folders, drag/drop, a sequential batch queue, per-file progress/results, retry, and duplicate detection by SHA-256. Each file may be up to 1 GiB. Password-protected/DRM books may fail; the batch continues.

## Storage and behavior

Originals, converted EPUBs, covers and the atomic import catalog are under `/mnt/data/survival-library/imported-books/`. Existing 119 books and originals remain in place. The shelf and reader fetch `/api/library/books`, combining the base catalog with imports. MOBI originals are retained and an EPUB copy is used for reading. Identical files are skipped, including files matching the baseline asset map. Different editions or formats can appear as separate titles; title-based merging is not automatic.

Uploads add books to the website, not to Open WebUI's AI/RAG collections. Metadata editing, AI indexing, authentication beyond the site's existing trusted-LAN access, and portable mount activation are separate work. Any device allowed to access the existing LAN site can use this upload page. The backend listens only on 127.0.0.1:8123, rejects cross-origin upload requests, and has systemd filesystem/network restrictions. Keep the upload page open until its queue completes. For interrupted batches, choose files again; completed hashes are skipped.

## Verification and recovery

`python3 test_uploads.py --require-mobi` uses a temporary directory; it never imports fixtures into the real library. It tests valid EPUB/PDF/MOBI imports, conversion/original retention, metadata/covers, duplicates (including pre-existing books), rejection of malformed files and foreign origins, and the stored catalog. Calibre is required for full checks. Before installation, all checks except actual MOBI conversion passed on MAHA. JavaScript and shell syntax also checked. Static upload-page layout checked in the browser; live browser upload and phone acceptance remain pending activation.

Service diagnostics: `systemctl status maha-library-api.service` and `journalctl -u maha-library-api.service -n 60`. Installation prints a backup directory. Original files can be downloaded through their stored `originalUrl`; MOBI reading links use the converted EPUB. Include the entire imported-books directory in future storage migrations and backups. Current portable-storage config must gain upload routes before it replaces Nginx configuration.
