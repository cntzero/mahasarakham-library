# Music visualizer

The listening shell loads player-visualizer.js and player-visualizer.css. One Web Audio source analyses the existing Music frame audio, without a second player. The expanded spectrum and five compact bars follow the selected theme.

Animation stops on pause, end, hidden tabs and reduced motion. Reduced motion leaves static compact marks and hides the expanded spectrum. Rendering is capped near 30 frames per second and pixel density at 2. No external library or service is used.

Validated in browser with a synthetic tone and automated checks for pause, reduced motion, hidden tabs and source reuse. Real MP3 playback needs a smoke test after deployment. Existing same-origin MAHA audio is supported; external audio would require CORS support.
