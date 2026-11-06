# MAHA audit remediation — 4 November 2026

Status: implemented and tested in staging; production installation requires the owner's sudo password.

## Included

- F1: root-relative login assets, safe local return destination, nested-path normalization, return to requested content after login. External destinations and API endpoints are rejected by redirect validation.
- F2: darker muted and accent text in application HTML/CSS, preserving the brand palette.
- F3: named book/detail/removed-book and remote-device dialogs.
- F4: MAHA archive reader with persistent return navigation and local full-text Kiwix search. Captured scripts/forms are sandboxed. Original views remain available.
- F5: article-first preserved-page filtering, with an explicit complete-capture view. No files removed.
- F6: missing-image notices and a simplified reading view, verified against the actual rainwater article. This makes incomplete captures usable and explicit; it does not recreate missing original images.
- F7: clear-all-filters recovery resets category, text, tags, and date.
- F8: independent pristine/new-upload/enabled HTTPS fixtures; the repaired suite passes on MAHA.
- F9: distinct missing-book/no-EPUB errors and disabled controls while loading or unavailable.
- Additional: per-tab catalog filter/scroll restoration; reader return points to Library; private-page noindex metadata.

## Validation

- Frontend syntax and targeted safe-redirect/article-filter/loading-control regressions pass.
- HTTPS certificate/IP, Nginx syntax, rule preservation and idempotence suite passes on MAHA without changing live Nginx.
- Accounts/classification, access workflow, collection controls, and full EPUB/PDF/MOBI import fixture suites pass.
- Browser: empty-search recovery restores 120 books; unknown book has accurate error and disabled controls; article-first/raw selector works; actual Kiwix full-text search returns results inside MAHA; actual preserved article opens in simple view with body text rather than sidebar teasers; no shell overflow at measured 390 CSS pixels.
- Existing account/database/book/archive data were not changed by tests. Staged source files were copied to `/mnt/data/projects/maha-library/`.

## Installation

Run on MAHA:

```bash
sudo bash /mnt/data/projects/maha-library/upload-service/install-audit-fixes.sh
```

The installer runs the repaired HTTPS test, backs up the current application pages, installs staged HTML/CSS/JS, checks Nginx and public login assets, and restores application files on failure. It does not change Nginx, accounts, router rules, source books, ZIMs, or preserved websites. It prints a backup directory. Refresh the browser with Ctrl+F5 afterward.

## Remaining operational checks and deferred recommendations

- Final live HTTPS/sign-in/return-to-article verification follows installation. Unit/browser staging results are not a claim that production has already changed.
- Open WebUI HTTPS needs its own proxy/base-URL/session and firewall review; the existing AI endpoint has not been changed.
- Real guest VPN isolation, physical-phone/screen-reader testing, restore drills and full-library integrity remain operational acceptance work.
- Missing original captured images cannot be reconstructed from absent files. The reader now reports them rather than claiming complete content.
- AI-generated tag quality still requires model/content evaluation; no blanket reclassification or existing metadata rewrite was performed.
- No production users or invites were created or revoked merely to test onboarding. Existing isolated suites verify these backend paths; a full browser invitation acceptance journey remains a separate acceptance check.
