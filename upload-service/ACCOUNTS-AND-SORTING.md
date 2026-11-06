# MAHA sorting, accounts and private access

**Activation update:** the router's WireGuard VPN is working. Use `LOCAL-ACCOUNTS-WIREGUARD.md` and `enable-library-accounts.sh` instead of the historical Tailscale instructions below. `enable-private-access.sh` has been retired and will not install a VPN.

Prepared 4 November 2026; activation requires the owner's administrator session.

## 1. Apply classification and catalog editing

    sudo bash /mnt/data/projects/maha-library/upload-service/install-uploads.sh

Imports become readable first under **To be sorted**. A persistent, single-worker queue uses the existing local Ollama `qwen3.5:4b` model to inspect metadata and a bounded text sample. EPUB and converted MOBI use reading-order sections; PDFs use the first eight pages. No cloud model is called. An ambiguous result, insufficient text, timeout or model failure leaves the book in To be sorted. Self-reported model confidence is a routing heuristic, not a calibrated probability. No upload fails because classification cannot run. Existing curated baseline categories are retained; earlier imports are queued on startup. Existing books can also be explicitly reclassified.

The shelf gains category filters, tag search, **Edit category & tags**, and **Try AI sorting**. Custom categories and tags are allowed. A revision check prevents a late AI response from overwriting a newer manual edit. Category/tag overrides and queue state persist under `imported-books/classification.json`; book originals are unchanged. Classification is separate from WebUI RAG ingestion.

Until accounts are activated, the existing trusted-LAN access behavior remains in place. After activation, only Super users see management controls and all write routes enforce that role on the server.

## 2. Enable accounts and private HTTPS

    sudo bash /mnt/data/projects/maha-library/upload-service/enable-private-access.sh

This installs Tailscale from its official Ubuntu repository if missing, asks the owner to follow the Tailscale sign-in/HTTPS authorization links, and creates the first local Super user with an email and password entered privately at the terminal. No account credentials are sent to this chat. Existing unrelated Tailscale Serve settings are preserved by stopping for review. Tailscale Serve exposes the library only inside the private VPN; no Funnel/public service or router port forwarding is configured.

Two roles:

- **Super user:** upload books, edit/retry sorting, invite users, change roles, deactivate accounts.
- **User:** browse, search and read.

Sessions are cookie based (Secure, HttpOnly, SameSite=Strict) with expiry and revocation. Passwords use salted PBKDF2 hashes; invitation/session tokens are stored as hashes. Login attempts are throttled. Invitations expire after seven days and work once. The last active Super user cannot be removed. Users can be invited as either role. Users → Create invitation → Email invitation opens the owner's email app with a prepared link; Copy invitation link is also available. No SMTP delivery or VPN membership invitation is automatic. Remote recipients separately need permission to join/access the private VPN.

Nginx protects original books, imported books, catalog JSON, Kiwix and pages, rather than merely hiding buttons. Sign-in assets and the backend's explicitly checked authentication routes remain accessible. Loopback-only services stay loopback-only. Activation validates Nginx, API/session routing and rejection of unauthenticated catalog/original access, with configuration rollback on failure. The existing Open WebUI on port 8080 is a separate authenticated application; this change does not proxy it for remote access.

## 3. Trust local HTTPS on LAN clients

VPN access uses Tailscale's HTTPS name/certificate. Offline LAN access uses `https://192.168.1.64/` and a dedicated private CA. The public trust certificate is exported to:

    /mnt/data/projects/maha-library/maha-local-root-ca.crt
    Z:\projects\maha-library\maha-local-root-ca.crt

After verifying the SHA-256 certificate fingerprint printed by setup, the owner can trust this public certificate on their Windows account:

    certutil -user -addstore Root "Z:\projects\maha-library\maha-local-root-ca.crt"

This explicitly trusts MAHA's CA to issue certificates on that device. Do not import or distribute the CA's private key. Other devices need their own one-time trust installation. Do not bypass browser certificate warnings. LAN server certificates renew locally via a weekly systemd timer, without internet; the private root's ten-year lifetime still requires eventual renewal. Tailscale enrollment, invitations into the VPN, and VPN certificate renewals require internet, but local HTTPS/account checking does not depend on those services. Actual disconnected acceptance tests remain required after activation.

## Verification and backup

Isolated server tests passed for EPUB/PDF/MOBI ingestion, original retention, duplicates, invalid files, model/queue failure without blocking uploads, persistent jobs, resumed jobs and manual override precedence. Account tests passed for one-use invitations, hashed secrets, reader/super authorization, logout, disabling accounts and last-super protection. A real local-model sample classified the solar-power book into Energy & workshop. UI controls inspected in the local preview; syntax checks passed. Full VPN enrollment, local certificate trust, protected-route checks and authenticated browser acceptance remain pending owner activation.

Back up `/srv/maha-library-api/accounts.sqlite` consistently (SQLite backup API or while the service is stopped), `/etc/maha-library/pki/` securely including private keys, Nginx/systemd settings, and the entire `survival-library/imported-books/` tree. These are outside the old Open WebUI-only backup. Protect copies of passwords' hashes and CA private keys. Do not expose auth state or CA private keys through the portable media website. Review the older portable-storage Nginx template before using it: it must retain the upload/account routes and protection. Current stable-media bind activation remains separate work.
