# Local accounts and HTTPS with the router's working WireGuard VPN

This supersedes the Tailscale-specific activation instructions in ACCOUNTS-AND-SORTING.md. No Tailscale or Headscale service is required or installed by the revised installer.

Run on MAHA:

    sudo bash /mnt/data/projects/maha-library/upload-service/enable-library-accounts.sh

The installer updates staged application files if required, runs isolated account tests, prepares the private HTTPS certificate and local renewal timer, and asks for the first Super user's email/password at the terminal. Existing accounts are preserved on subsequent runs. It backs up Nginx/account settings before activation, preserves the existing LAN and WireGuard 10.5.5.2 allow rules, enables cookie-based local accounts, validates HTTPS and unauthenticated file protection, and restores the previous configuration if activation fails. The old enable-private-access.sh is retired and exits with a pointer to this installer.

Both LAN and VPN devices then use:

    https://192.168.1.64/

Each device needs to trust the generated MAHA public root certificate once. It is exported to `/mnt/data/projects/maha-library/maha-local-root-ca.crt` (Windows mapped path `Z:\projects\maha-library\maha-local-root-ca.crt`). Compare its SHA-256 certificate fingerprint with the one printed in the MAHA terminal. Transfer the public certificate through the existing SSH/file-share connection. Do not bypass browser certificate warnings or distribute the private CA key.

Windows Chrome/Edge can use a current-user trusted-root import after the owner chooses to trust MAHA's CA:

    certutil -user -addstore Root "Z:\projects\maha-library\maha-local-root-ca.crt"

This trusts this CA to issue certificates for that Windows account. Android/iOS devices require a separate trust installation through their device settings. Exact phone instructions will follow after the server creates the certificate. The certificate authority and renewal process stay on MAHA and work without internet. Router VPN settings are not modified. The existing HTTPS app uses the same IP address over WireGuard as on the LAN.

Super user: manage books, categories/tags, imports, invitations and account roles/status. User: browse/search/read. Invitations expire in seven days and are one-use; Email invitation opens a prepared message in the owner's email client. VPN device profiles remain separate from library users. Each new VPN device will also need its authorized address added to the server allow rules; only the first phone is currently authorized. Library roles do not restrict other home-network services at the router level.

Still pending: owner activation, first Super user credentials, desktop/phone certificate trust, authenticated browser and cellular acceptance checks. Independent tests passed for certificate/IP verification, configuration idempotence/WireGuard-rule preservation, Nginx syntax, local AI classification and failure fallback, and role/session/invitation controls. GoDaddy DNS is unchanged; future stable-domain/dynamic-DNS work remains separate. Open WebUI on port 8080 has separate authentication and is unchanged.

Backups must include the imported-books tree, `/srv/maha-library-api/accounts.sqlite` consistently (SQLite backup or stopped service), `/etc/maha-library/pki` including private keys stored securely, and Nginx/systemd settings. The older Open WebUI-only backup does not include these. Preserve account/upload protection and authorized VPN rules in any future portable-storage Nginx migration.
