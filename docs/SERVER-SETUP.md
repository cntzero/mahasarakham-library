# Stand up a MAHA server

This is the fresh-host runbook. The source snapshot came from Ubuntu 24.04 LTS and Python 3.12. The new preparation script has syntax/static checks; a complete install on a separate empty VM has **not** been performed. Do not run the fresh-host installer on the current MAHA server.

## 1. Requirements and decisions

- Ubuntu Server 24.04 LTS, systemd, administrator/sudo access, a stable LAN IPv4 address, working DNS, and synchronized time.
- Planning estimate: 2 CPU cores, 4 GB RAM, 20 GB free OS disk, plus storage for your media, conversions, databases, and backups. These are not benchmarked minimums. OCR and local AI require additional resources.
- Mount a persistent data volume at `/mnt/data`. Configure it by UUID in `/etc/fstab`, test `mount -a`, and verify `findmnt /mnt/data` before installation.
- Choose a LAN subnet, e.g. `192.168.1.0/24`, service user, e.g. `maha`, and server address. Existing utilities assume the storage paths in this guide.
- Keep the site on a trusted LAN/private VPN. Do not forward its ports to the public Internet. Nginx serves HTTPS; the API and Kiwix bind loopback only.
- GitHub clone access or a reviewed source ZIP. No Node build step is required to run the site.

## 2. Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y git nginx python3 python3-pil python3-mutagen calibre poppler-utils libchromaprint-tools openssl curl rsync sqlite3
sudo useradd --system --user-group --home-dir /srv/maha-library-api --shell /usr/sbin/nologin maha
```

Skip `useradd` if that user already exists. Calibre supplies MOBI conversion; Poppler supplies PDF rendering; Pillow supplies image handling; Mutagen reads audio metadata; `fpcalc` produces recognition fingerprints. Install Node separately only for JavaScript source checks. Kiwix/OCR/local AI are optional.

```bash
python3 -c 'import PIL,mutagen,sqlite3'
command -v ebook-convert pdftoppm fpcalc nginx
findmnt /mnt/data
df -h /mnt/data
```

## 3. Clone at the expected staging path

```bash
sudo mkdir -p /mnt/data/projects
sudo chown "$USER":"$USER" /mnt/data/projects
cd /mnt/data/projects
git clone https://github.com/cntzero/mahasarakham-library.git maha-library
cd maha-library
```

Authenticate with your own GitHub account; never put a token in the clone URL. Alternatively extract the source ZIP as `/mnt/data/projects/maha-library`. On a shared server, assign only this project directory to your operator rather than changing ownership of other projects.

## 4. Prepare source and services

Substitute your LAN address and subnet:

```bash
sudo env MAHA_SERVICE_USER=maha MAHA_LAN_IP=192.168.1.64 MAHA_LAN_CIDR=192.168.1.0/24 bash deploy/install-source.sh
```

This refuses an existing `current` deployment, copies API modules, creates a static release and `current` symlink, initializes missing catalogs as empty arrays, and prepares Nginx/systemd definitions. It does not start services. No media or user databases come from Git.

Create the first MAHA super user interactively:

```bash
sudo -u maha env MAHA_AUTH_DB=/srv/maha-library-api/accounts.sqlite python3 /opt/maha-library-api/accounts.py
```

Enter your email and a MAHA password of at least 12 characters at the hidden prompts. This is independent of your GitHub password. No default password is shipped.

## 5. Set up HTTPS and client trust

`upload-service/setup-local-tls.sh` is the existing TLS creation/renewal utility. **Before running it**, inspect its IP address and DNS subject alternative name and replace the original `192.168.1.64` / `MahaSarakhamUbuntu` values if your host differs. Keep its certificate/export paths consistent with the Nginx template.

```bash
sudo bash upload-service/setup-local-tls.sh
```

It creates a private root CA and server certificate, installs a renewal helper/timer, exports the public CA certificate to `/mnt/data/projects/maha-library/maha-local-root-ca.crt`, and prints its SHA-256 fingerprint. Confirm the timer is enabled:

```bash
systemctl list-timers maha-local-tls-renew.timer
```

Copy **only the public CA certificate** to client devices. Verify its fingerprint against the server output, then trust it as a root CA in each operating system/browser. Do not bypass certificate warnings. Keep `ca.key` and `server.key` private and in an encrypted offline backup. They must never be committed to Git. Renewal must reuse the existing CA; changing the LAN IP requires a new server certificate with the new SAN.

## 6. Start the API, then Nginx

```bash
sudo systemctl enable --now maha-library-api.service
curl --fail http://127.0.0.1:8123/api/library/health
sudo ln -s /etc/nginx/sites-available/maha-library /etc/nginx/sites-enabled/maha-library
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl restart nginx
curl --cacert /mnt/data/projects/maha-library/maha-local-root-ca.crt --fail https://192.168.1.64/api/library/session
```

Use your selected IP in the last command. Review existing enabled sites before adding the link. Remove only an unwanted default-site symlink if it conflicts; preserve unrelated sites. The template permits the chosen LAN subnet and loopback, not the original VPN addresses. Add a deliberate VPN subnet allowance if needed. If a firewall is enabled, preserve SSH access and allow TCP 80/443 only from your LAN/VPN. Keep 8123 and 8091 private.

Visit `https://YOUR-LAN-IP/`, sign in, and verify the empty Books/Music pages. Upload one disposable EPUB/PDF and MP3, test reading and playback, then import or restore your real collection. See [IMPORTS.md](IMPORTS.md).

## 7. Optional music workers and local AI

```bash
sudo systemctl enable --now maha-music-artwork.service maha-music-identification.service
systemctl status maha-library-api.service maha-music-artwork.service maha-music-identification.service --no-pager
```

Recognition needs outbound HTTPS to AcoustID and MusicBrainz; artwork uses Cover Art Archive and approved archive hosts. As a super user, open Identify & review → Recognition setup and save an **AcoustID application API key**. Do not commit the key. Only an audio fingerprint is sent, not the MP3; metadata changes still require explicit review and Apply. Provider outages remain possible.

Local AI tagging/placeholder generation is optional. Inspect `music_tag_worker.py`, `music_art_worker.py`, and `classification.py` for their local Ollama model/URL before installing a model. Core playback and uploads do not require Ollama or Open WebUI. Do not expose their ports publicly.

## 8. Optional knowledge, preserved web, OCR, and VPN

- **Kiwix:** install `kiwix-tools`, store separately downloaded `.zim` files under `/mnt/data/kiwix`, and run `kiwix-manage /mnt/data/kiwix/library.xml add /absolute/path/archive.zim` for each archive. Replace `@SERVICE_USER@` in `deploy/systemd/maha-kiwix.service`, install it to `/etc/systemd/system`, reload systemd, then enable/start. Test `curl -I http://127.0.0.1:8091/kiwix/`. No ZIM data is shipped.
- **Existing books/web:** restore media into the alias paths in the Nginx template and restore matching private catalog manifests. Empty manifests are valid; do not restore entries without their files.
- **OCR:** selected `tools/content` jobs need extra tools such as PyMuPDF/Tesseract. Review each script's imports and fixed paths before use; they are not core startup dependencies.
- **VPN/DDNS:** follow `ddns/README.md` only if you want that original WireGuard/router/GoDaddy arrangement. It is host/domain-specific, not required to start MAHA. Tokens stay in root-only files outside Git.
- **Portable storage:** read `portable-storage/README.md`. Reconcile its historical Nginx configuration with current login protection before using it.

## 9. Acceptance before calling a new server ready

1. Reboot; verify the data mount and every enabled service.
2. Test unauthenticated access: protected pages/media must deny access or redirect to login. Check login and session behavior.
3. Test upload, search, reading, original download, album playback, and docked playback while reading.
4. Verify persisted favorites/playlists and selected-field identification scope.
5. Check desktop/phone, keyboard/Escape, light/dark themes, and zoom/reflow.
6. Make and test a database/media backup before bulk imports or permanent deletion.

See [OPERATIONS.md](OPERATIONS.md) for updates, backups, recovery, and troubleshooting. Do not run all historical `install-*.sh` files: some overwrite newer assets and assume old deployment state.
