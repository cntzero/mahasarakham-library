# Architecture and storage

## Request path

Browser → LAN/VPN Nginx HTTPS → static `dist/` assets, authenticated media aliases, or loopback Python API on `127.0.0.1:8123`. Nginx uses `/api/library/auth-check` for protected pages/media. Public login assets and session/login API routes remain reachable so a user can authenticate. The API performs its own permission checks on mutations.

`listen.html` is the persistent navigation shell. Its Music iframe owns the original audio element/queue; a separate page iframe displays books, readers and other destinations. The dock controls the original Music instance. Playback survives internal navigation in that tab, not tab closure/full refresh. Shared CSS/JS owns catalogs, discovery, dialogs, filters, themes and accessibility affordances.

The Python API uses standard-library HTTP handling/SQLite plus Pillow and Mutagen. Modules separate books, accounts, access requests, personal library/playlists, music grouping/bulk changes/downloads/merges, and identification. Recognition/artwork workers run as separate services with outbound access; the API service is network-restricted to localhost.

## Paths

| Path | Purpose | Back up? |
|---|---|---|
| `/mnt/data/projects/maha-library` | Source/staging checkout, utility scripts | Git plus untracked local configuration |
| `/srv/www/maha-library/releases/*/dist` | Versioned static releases and private baseline manifests | Source is in Git; keep private manifests separately |
| `/srv/www/maha-library/current` | Symlink to active release | Record target for rollback |
| `/opt/maha-library-api` | Installed Python modules | Rebuild from Git; retain version information |
| `/srv/maha-library-api/accounts.sqlite` | Users, password hashes, sessions, invitations | Yes, encrypted/private |
| `/mnt/data/survival-library/imported-books` | Immutable originals, conversions, covers, imported catalog and metadata | Yes |
| `/mnt/data/survival-library/music` | MP3s, covers, SQLite catalog, source mappings, jobs, identification settings/backups | Yes |
| `/mnt/data/kiwix` | ZIM archives and Kiwix `library.xml` | Yes, or retain download inventory |
| `/mnt/data/survival-library/web-articles` | Preserved website files | Yes |
| `/etc/maha-library/pki` | Private CA/server keys and certificates | Encrypted/offline backup; never Git |
| `/mnt/data/projects/maha-library/windows-music-import` | Windows receiver progress DB and temporary transfers | Keep progress DB for resumable imports |
| `/mnt/data/backups` | Upgrade rollback material | Separate backup destination also required |

The original book families also use `humble-books`, `bushcraft`, `backwoods`, and `who-wash` directories under `/mnt/data/survival-library`; see Nginx aliases. Runtime catalogs map URLs to those files. Git intentionally does not contain the catalogs or media.

## External dependencies

AcoustID receives audio fingerprints for explicit identification. MusicBrainz supplies release metadata; Cover Art Archive supplies artwork. Originals are not uploaded. Optional local AI talks to a local Ollama service. Optional DDNS updates a configured GoDaddy record. The repository contains code for these integrations, not their credentials or data.
