# Changelog

## 1.0.0 — 2026-11-06

First tagged MAHA source release, including the documented self-hosted application and import utilities.

- Responsive catalog layouts and Daily Discoveries for Books, Music and Knowledge.
- Persistent docked music player with artwork, favorites, queue, album and playlist browsing.
- Theme-aware audio spectrum in a lighter framed display, plus five compact playback bars.
- Animation pauses with playback, hidden tabs and reduced-motion settings.
- Outside-click dismissal for expanded player details and a contextual Music library button.
- Base-address navigation opens Home rather than an empty frame.
- Server setup, imports, operations and visualizer documentation included.

Validation: JavaScript syntax checks, discovery consistency checks and Knowledge discovery tests; browser prototype playback/pause and navigation checks; automated visualizer reduced-motion, pause, hidden-tab and source-reuse checks. The visualizer browser tests used a synthetic tone; deployed MP3 playback has not been independently verified for this release.

Media, private catalogs, databases, credentials and certificates are excluded. Deploying source does not restore the collection; follow docs/SERVER-SETUP.md and restore or import data separately.
