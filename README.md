# MAHASARAKHAM (MAHA)

Private, self-hosted home library for books, offline knowledge, preserved websites, and music. Includes the responsive interface, persistent music player, local accounts, imports, playlists/favorites, metadata review, artwork workers, deployment references, and tests.

Current source release: **v1.0.0**. See [release notes](CHANGELOG.md) and [music visualizer details](docs/MUSIC-VISUALIZER.md).

## Screenshots

![MAHA Home](docs/screenshots/home.png)

[View the screenshot gallery](docs/SCREENSHOTS.md): books, music, album details, the persistent player, offline knowledge and phone layout. Captured from the real self-hosted server.

## Start here

- [Complete server setup](docs/SERVER-SETUP.md): requirements and all steps for a clean Ubuntu host.
- [Imports and maintenance utilities](docs/IMPORTS.md): books, MP3s, Windows transfer, covers, preserved web, ZIMs, and duplicates.
- [Architecture and storage](docs/ARCHITECTURE.md).
- [Operations, backup, restore, troubleshooting](docs/OPERATIONS.md).
- [Development and checks](docs/DEVELOPMENT.md).
- [Snapshot and exclusions](docs/REPOSITORY-CONTENTS.md).

## Layout

`dist/` is the browser application; `upload-service/` contains the Python API, import commands, workers and tests; `upload-service/site/` mirrors the deployed browser assets for historical installers. `deploy/` provides the clean-host procedure and configuration references. `tools/` contains recovered offline-content and Windows import utilities. `ddns/` and `portable-storage/` are optional environment-specific tooling.

This repository deliberately contains no private media, accounts/session databases, API keys, TLS keys/certificates, or live catalog manifests. Empty catalogs are created during setup. A clone reproduces the software, not the collection: restore data separately or import new content.

Historical `install-*.sh` scripts are preserved for maintenance history. **Do not run all of them on a fresh server.** They assume different older layouts and may overwrite newer assets. Follow `docs/SERVER-SETUP.md` instead.

The initial snapshot is based on installed server files on 6 November 2026, supplemented by import utilities and source tests from the working project. No open-source license grant is added; bundled third-party licenses remain with their libraries.
