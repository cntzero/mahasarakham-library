# MAHA GoDaddy VPN dynamic DNS

Target: the existing `vpn.discerntechnologies.com` A record only. GoDaddy authoritative DNS was verified at 68.234.171.235 with TTL 600 on 4 November 2026. Existing root/www/email records are not managed by this updater.

Install on MAHA:

    sudo bash /mnt/data/projects/maha-library/ddns/install-ddns.sh

Paste the saved GoDaddy Personal Access Token at the hidden terminal prompt, not in chat or a command-line argument. Required GoDaddy scopes: `domains.domain:read` and `domains.dns:update`. The token's real scope can cover DNS throughout the account; restriction to this domain/name is enforced by this updater's code. Its token is saved root-only at `/etc/maha-vpn-ddns/token`; systemd passes a private credential copy to a DynamicUser oneshot service. No token is written to source, shell command arguments or normal logs. The root token file is intentionally outside the portable-media tree.

Setup runs tests, checks access read-only, then starts one update and enables a five-minute timer. The updater consults two HTTPS IPv4 echo services (api4.ipify.org and checkip.amazonaws.com), requires them to agree on a public IPv4 address, queries the exact existing A/name match through GoDaddy v3, and uses PUT on that record's ID only if its IP differs. It preserves the record TTL and verifies the resulting IP through GoDaddy. It does not create/delete records, replace a whole zone, change nameservers, or update @/www. Missing/duplicate/invalid records or IP disagreement stop without a write. Redirected API calls are rejected to avoid forwarding credentials elsewhere. A before-update snapshot and last successful status are stored in `/var/lib/maha-vpn-ddns/` (DynamicUser storage may physically live under /var/lib/private).

Checks passed without real credentials/DNS mutation: update/no-op/check-only behavior; target/path restrictions; backup of old IP; invalid/private IP rejection; missing/duplicate/wrong-name/wrong-type handling; two-source agreement; preserved TTL; secret-safe errors. Both live IP echo services returned 68.234.171.235. Live authenticated API checking and timer activation are pending the owner's local token entry. No DNS mutation was attempted by the agent.

After successful setup, edit only the phone WireGuard peer Endpoint to `vpn.discerntechnologies.com:51820`. Keep all keys, addresses and Allowed IPs unchanged. Test over cellular again. This hostname is the VPN endpoint, not the library's web address; the library remains `https://192.168.1.64/` over the LAN/VPN. Router WireGuard and the offline library do not depend on the updater to operate at the current address. Remote DNS changes require internet, and resolver caches can retain the old IP for the TTL. Existing VPN clients may need reconnecting to pick up a changed endpoint address.

Diagnostics:

    systemctl status maha-vpn-ddns.timer
    journalctl -u maha-vpn-ddns.service -n 30 --no-pager
    sudo cat /var/lib/maha-vpn-ddns/status.json

Renew the PAT before the expiration selected in GoDaddy. Re-run the installer to paste a replacement. Do not expose the token directory or private systemd credential paths through the website/Samba. Include the protected token in secure system configuration backups if desired; it is not included in the older Open WebUI backup. A failed service run retains prior DNS unless a PUT was submitted; API verification detects uncertain results, and the next run reconciles state by reading GoDaddy again.

API reference: https://developer.godaddy.com/en/docs/api-users/domains/manage/dns
