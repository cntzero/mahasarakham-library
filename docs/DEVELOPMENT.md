# Development and checks

The frontend is plain HTML/CSS/JavaScript; no build framework is required. The API/worker scripts use Python 3.12 on Ubuntu. Install runtime dependencies in SERVER-SETUP. Windows is suitable for editing and JS/static checks; media and service integration tests should run on Linux.

`dist/` is the canonical browser source in this snapshot; mirror changes to `upload-service/site/` until historical installers are retired. Keep shared catalog/discovery/dialog geometry in the common stylesheets (see AGENTS.md), preserve native semantics, and test desktop/phone plus themes and zoom.

## Local preview without private data

```bash
cp asset-map.example.json asset-map.json
printf '[]\n' > dist/catalog.json
printf '[]\n' > dist/archive-pages.json
python3 preview-server.py --port 8766
```

This is a read-only static preview, not the production API. API-backed features require the real service or a deliberate fixture server. Generated empty manifests are ignored by Git. Never put production accounts/media into a fixture server.

## Checks

```bash
python3 -m compileall -q upload-service tools
find dist -maxdepth 1 -name '*.js' -exec node --check {} \;
bash -n deploy/install-source.sh
python3 upload-service/test_music.py
python3 upload-service/test_music_bulk.py
python3 upload-service/test_music_identify.py
python3 upload-service/test_music_merges.py
python3 upload-service/test_personal_library.py
python3 upload-service/test_uploads.py --require-mobi
```

Other `test_*.py` files cover accounts, access workflows, duplicate handling, cache/downloads/artwork, HTTP behavior, and collection controls. Some require OS tools or specific fixtures; inspect their imports/top-level setup before running. Tests use temporary paths where designed; do not point them at production databases. `test_audit_ui.mjs` requires a compatible browser test environment. The `test_*.cjs` consistency tests resolve paths relative to this repository after the path normalization included in this snapshot.

Before publishing a commit, run `git diff --cached --stat`, inspect the staged filenames and `git status`, and confirm no media, keys, credentials, user databases or private catalogs are staged. Python syntax checks do not prove a fresh server installation or browser acceptance.
