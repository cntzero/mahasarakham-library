# Snapshot, provenance and exclusions

Created 6 November 2026 from the installed MAHA frontend and `/opt/maha-library-api` modules, staging utility scripts, recovered Windows/content import tools and local consistency tests. Installed application files take precedence over old upgrade bundles. New deployment templates/runbooks are included for reproducibility.

## Included

- HTML/CSS/JS application and EPUB/ZIP browser libraries with their bundled licenses.
- Python API, accounts/access controls, book/music import and metadata utilities.
- Music workers, grouping/merges/duplicates, playlist/favorite handling, tests.
- Windows sender/monitor and server receiver.
- Book-family/OCR/preserved-web/Kiwix preparation and transfer source.
- Original upgrade scripts and optional DDNS/portable storage tooling.
- Current readable Nginx/systemd references plus fresh-host templates and documentation.

## Excluded

Books, MP3s, audio fixtures, ZIMs, PDFs, video, cover images, captured website collections, generated catalog manifests, real asset maps, accounts/session databases, job/progress databases, virtual environments/wheels, logs/reports, TLS material, credentials/API settings and backup archives. `.gitignore` protects these classes; review staged content before every push. The example asset map is empty.

Some protected TLS renewal reference files were unreadable to the source-export account; the original TLS setup script regenerates the unit/timer. This does not include or copy private keys. Historical markdown notes are retained for context and may describe earlier states; the current runbooks take precedence.

No media restore or server installation was performed while creating this repository. The clean-host procedure is documented and statically checked, but not certified by a blank-VM deployment. The collection must be restored or reimported separately.
