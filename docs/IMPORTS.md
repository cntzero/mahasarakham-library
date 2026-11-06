# Import and content utilities

All imports operate on separately supplied files; no collection is in Git. Keep originals and a tested backup. Run tools as the configured service user where they write managed data. Many recovered scripts contain original fixed paths: inspect their constants before running them on another workstation.

## Books: supported browser workflow

Sign in as an allowed uploader → Books → Add books. Select files/folders or drag files into the queue. EPUB/PDF are supported; MOBI uses Calibre to make a readable EPUB while retaining the original. Server-side SHA-256 detects duplicates. The queue continues after a per-file error. A book upload is not an Open WebUI/RAG import.

Core implementation: `upload-service/server.py`, `classification.py`, `collection_controls.py`, and `dist/upload.js`. Imported originals, conversions, covers and catalog live under `imported-books`. Existing book-family manifests and `asset-map.json` must be restored separately if retaining old URLs/deduplication against pre-existing collections.

## Music on the server

The browser Add songs workflow accepts MP3s, files/folders and sequential batches. For bulk import from attached storage:

1. Inspect `upload-service/inventory_music.py` constants (`ROOT`, output path and excluded directories).
2. Run an inventory with Mutagen available. It is read-only with respect to source MP3s and writes `music-inventory.json`.
3. Review entries marked `include`, `review`, and `excluded`. The import script processes only `include`.
4. Run `upload-service/import_music.py` under the intended data owner, with correct paths/module imports. It copies/hashes through `music.add_file`, skips known file hashes, preserves source files, and writes `music-import-results.json` periodically.
5. Check errors and counts before rerunning. Do not blindly mark unclassified application/game audio for import.

```bash
cd /mnt/data/projects/maha-library/upload-service
sudo -u maha python3 inventory_music.py
# Review /mnt/data/projects/maha-library/music-inventory.json first.
sudo -u maha python3 import_music.py
```

Import ownership: browser imports use the signed-in user. Older command-line scripts may leave ownership unspecified or use a fixed owner. Review that before importing into a multi-user library. Run `python3 test_music.py` against temporary fixtures when changing import behavior.

## Windows → MAHA resumable MP3 transfer

`tools/windows/send_music.py` scans MP3s, streams them over SSH to `upload-service/receive_windows_music.py`, computes SHA-256, and writes progress/results locally. The receiver verifies hashes and keeps a server-side `windows-music-import/progress.sqlite` to resume completed transfers. The SSH account must be allowed to write the import state and managed music folders; the restricted `maha` system user has no login shell. Use a trusted SSH operator with the necessary directory permissions.

```powershell
python tools/windows/send_music.py --root 'E:\Music Collection' --ssh maha --output 'C:\MahaImportProgress'
powershell -File tools/windows/Watch-MahaMusicImport.ps1 -LogDirectory 'C:\MahaImportProgress' -Once
```

Configure `Host maha` in the Windows OpenSSH config for the intended operator/server and verify key-based login first. The receiver's path is `/mnt/data/projects/maha-library/upload-service/receive_windows_music.py`. It currently assigns imported tracks to owner ID 1; verify that ID belongs to the intended first administrator before use, or adapt it explicitly. Do not upload progress manifests/logs to Git: they contain private filenames. The sender's `--root`, `--ssh` and `--output` arguments replace the original workstation-specific constants.

## Metadata, artwork and duplicate utilities

| Utility | Purpose / precautions |
|---|---|
| `backfill-music-albums.py` | Backfill album organization; inspect scope before running on live metadata |
| `index_audio_duplicates.py` | Build audio-content duplicate index; distinct from whole-file SHA-256 |
| `follow_audio_duplicates.py` | Follow/process duplicate indexing; inspect mode/output paths |
| `music_tag_worker.py` | Optional local AI tag suggestions; manual user metadata takes priority |
| `music_art_worker.py` | Online artwork lookup / local placeholder path; optional network worker |
| `music_identify_worker.py` | Explicit fingerprint identification, release matching and review; never auto-applies |
| `music_merges.py` | Preview/confirm album merges and retain undo history through API |
| `music_bulk.py` | Server validation for batch tags/remove/delete; do not call directly without review |
| `fix-manual-title.py` | Historical one-title repair; contains case-specific assumptions, inspect first |
| `backfill-ai-sorting.py` | Historical book classification backfill; inspect paths and model settings |

Use the browser review flows for routine metadata/artwork changes. “Remove from library” retains managed media; permanent deletion does not. Identification can be scoped to one track even inside a large unknown-album group.

## Original collection preparation and knowledge imports

`tools/content/` preserves the recovered source preparation tools:

- `prepare_additional_epubs.py`, `prepare_backwoods.py`, `prepare_bushcraft.py`, `prepare_who_wash.py`: family-specific collection preparation.
- `check_epubs.py`: EPUB structure/reference audit.
- `extract_book_covers.py` and root `extract-book-covers.py`: thumbnail extraction; install-cover helpers publish prepared cover outputs. Check which family/input manifest each expects.
- `ocr_backwoods.py`: optional OCR/PyMuPDF preparation, potentially expensive.
- `split_ebook_sections.py`: generate section-sized book derivatives; retain originals.
- `prepare_web_mirror.py`, `preserve_web_mirror.py`, `catalogue_web_mirror.py`: prepare preserved-site files and their private catalog. Source URL lists and captured HTML/data are not included.
- `transfer_humble_originals.py`, `transfer_kiwix_archives.py`: transfer original collections; inspect SSH/destination constants.
- `package_libraries.py`: package prepared collections, not application deployment.

These are recovered utilities, not a universal content importer. Their embedded original paths and collection-specific rules are deliberately documented rather than silently executed. Some expect local dependency folders from the original workspace; install their declared imports in an isolated environment and adapt the paths before reuse. For Kiwix startup/catalog commands see SERVER-SETUP section 8. Keep `.zim` files and private `library.xml` outside Git.

## Installer inventory

`upload-service/install-*.sh` are historical incremental upgrades. They describe feature-specific copying/configuration and can help explain provenance, but must not be run as a blanket install sequence. `install-library-site.sh` assumes the original 119-book dataset and is not the fresh-server entry point. The supported fresh-host preparation entry is `deploy/install-source.sh` plus SERVER-SETUP.
