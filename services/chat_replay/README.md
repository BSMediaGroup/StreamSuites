# Chat Replay and Live Scaffolding (Runtime)

This directory now ships a single HTML surface that can present either **replay** or **live** visuals, plus an OBS overlay that reuses the same renderer and mock data. All assets remain static and avoid sockets, APIs, or backend wiring.

## Files and layout

- `templates/chat_window.html`: Unified window. Use `?mode=replay` (default) or `?mode=live` plus optional `?theme=`.
- `templates/chat_overlay_obs.html`: OBS/browser source-friendly overlay that reuses the renderer and honors `?theme=`.
- `templates/partials/theme_menu.html`: Theme selector markup kept from **Uiverse.io by Na3ar-17** (dropdown card structure preserved per requirement).
- `templates/partials/footer_replay.html`: Slim replay footer with theme selector and status pill.
- `templates/partials/footer_live.html`: Live footer with the required Lakshay-art input scaffold, emoji stub, and send icon.
- `static/chat.css`: Shared styling for chat layouts, avatars, badge row positioning, and footer chrome.
- `static/chat_live_input.css`: Adapted styling from **Uiverse.io by Lakshay-art** (layered borders and masking preserved, animation intensity reduced, StreamSuites color variables applied).
- `static/themes/*.css`: Theme token files (default, slate, midnight).
- `static/chat_mock_data.js`: Mock messages with avatars, platform diversity, and badge combinations; also exports the renderer used by all HTML surfaces.
- `contracts/chat_message.schema.json`: Placeholder neutral message contract.

## Reference components (why they remain intact)

- **Theme selector (Na3ar-17)**: The dropdown uses the original `.card`, `.list`, `.element`, and `.separator` structure from Uiverse. Only colors, borders, and typography were adjusted to match StreamSuites’ dark palette and fonts. The reference is cited directly to honor the locked visual contract and avoid refactoring risk.
- **Live input (Lakshay-art)**: The footer input keeps the layered borders, masking, and icon placement from the Uiverse example. Animations were softened and gradients retuned to StreamSuites blues, but the structural HTML/CSS remains to satisfy the locked baseline.

These components were not rewritten to prevent drift from the authoritative visuals and to keep future QA aligned with the provided references.

## Modes and roadmap

- **Replay mode**: Shows mock messages, timestamp toggles, autoscroll controls, pause/clear, and a footer theme selector. Platform/role badges render in the top-right corner of each message for OBS-safe alignment.
- **Live mode**: Shares the same renderer and mock data but swaps in the live input footer and disables replay controls. Emoji and send actions are stubbed only; no network traffic is emitted.
- **Overlay**: The OBS overlay renders replay-only content with top-right badge placement, avatar fallbacks, and theme support. Footers and inputs are omitted for capture cleanliness.

Future integration can replace `chat_mock_data.js` with runtime-fed data matching `contracts/chat_message.schema.json`, preserving the avatar column and badge layout guarantees without altering this scaffold.
