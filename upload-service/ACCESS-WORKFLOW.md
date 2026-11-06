# Guided access management

Prepared 4 November 2026. Apply on MAHA:

    sudo bash /mnt/data/projects/maha-library/upload-service/install-access-workflow.sh

Then refresh the library and open **Users** as a Super user. The old Users URL redirects to `access.html`. The complete standalone, printable procedure is `access-procedure.html`; it remains available offline on the library server. This document records implementation/operational details, while that page is the administrator's step-by-step procedure.

## What is saved

Setup plans record an email, intended role and local/remote access choice. Device records contain only a human-readable device label, exact router profile name, assigned 10.5.5.x VPN address, and owner-recorded completion/removal steps. A person's phone/laptop have separate records. Existing router profiles can be recorded without recreating them. Plans and devices can be resumed after closing the browser. Events record who changed a plan, checklist or account, and when. No router private keys/configuration/QR files are collected or stored by this feature.

Library status is read from real account/invitation records. Router/device progress is explicitly labeled as owner-recorded, not live router telemetry. A role or local/remote label does not enforce router-level network isolation. The workflow does not create/delete router profiles or change home-network access remotely. A library User role limits the library only. Before inviting people who should not have home-network access, add appropriate router/network isolation separately.

## Invitation procedure

Save the person's plan. For each remote device, follow the embedded router instructions, privately deliver its WireGuard profile, and save the profile's real name/address. Download the public MAHA certificate using the authenticated button. Create the library invitation when ready. Email invitation opens a prepared message in the owner's email app; the owner attaches the public certificate and sends it. VPN credentials are delivered privately. The generated invitation link is held only in that browser page's memory and shown only after creation; it is not saved in plaintext. Reloading loses it; create a replacement if needed. Replacement invalidates the prior pending link. Links expire after seven days and are one-use. Existing accounts need device setup, not another account invitation.

The recipient trusts the certificate, uses the home network or VPN, accepts the link and sets their password. Verify library login and a book over cellular with Wi-Fi off; for a reader, verify management functions are unavailable. Record the successful test. The service stores acceptance status automatically but relies on the owner's confirmation of device/network tests.

## Removing access

Disable library access cancels outstanding invitations, disables the account, revokes all its sessions immediately, and flags remaining device profiles for router removal. The last active Super user is protected. The owner must separately delete each actual WireGuard profile on the router, then record those removals. Merely marking a checklist does not revoke network credentials. Removed records stay as history; reused router addresses are allowed only once the previous record's removal is recorded. Re-enabling a library account does not silently reactivate removed VPN records.

## Deployment and data

The installer requires accounts/HTTPS already enabled. It runs isolated migration/permission/workflow tests, takes a consistent SQLite backup plus application/UI/Nginx backups under `/srv/maha-library-api/backups/access-workflow-*`, installs the additive database migration and UI, and adds an allow rule for `10.5.5.0/24` to the existing LAN/VPN Nginx policy. This avoids a new root configuration change for every router-authenticated VPN device. The existing owner phone 10.5.5.2 rule is retained. Public addresses remain denied. Library authentication and Super user write checks remain enforced. No router or DNS settings are changed.

Account hashes, sessions and existing users are preserved. New tables are `access_people`, `vpn_devices`, and `access_events` in `/srv/maha-library-api/accounts.sqlite`; a partial unique index prevents the same non-removed VPN address being recorded twice. A rollback restores application/static/config files while retaining backward-compatible added tables; it does not overwrite newer sessions/accounts using an older database snapshot. Keep the protected SQLite backup for manual recovery if needed. All such backups are on the ext4 SSD, outside the public/portable media tree.

## Validation

Isolated backend checks cover old-account migration, reader/anonymous rejection for all new administrative APIs, saved plans and per-device state, invalid/mismatched/duplicate addresses, canceled invitations, session revocation, explicit router-removal tracking, removed-record history, reused addresses, secret exclusion from overview responses and last-Super protection. Existing account and upload/classification checks are also retained. A disposable localhost UI fixture verified choosing a person, saving a device/checklist and restoring saved values; the page and dialog fit a 390px phone viewport with no horizontal overflow. Fixtures used synthetic people only and made no real account/router/email changes. Live authenticated acceptance remains pending owner installation.

Useful URLs after installation:

- `https://192.168.1.64/access.html` — guided Super user workflow.
- `https://192.168.1.64/access-procedure.html` — printable offline procedure.
- `/api/library/access` — Super-user-only plans, statuses and recent action history.
- `/api/library/trust-certificate` — authenticated public certificate download; never a private key.

The VPN endpoint stays `vpn.discerntechnologies.com:51820`; the library stays `https://192.168.1.64/`. Keep dynamic DNS and token renewal maintained separately. Future portable-storage deployments must retain authentication/upload routes and the authorized VPN range.
