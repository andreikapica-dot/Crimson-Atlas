# Changelog

All notable changes to Crimson Atlas are documented here in release order.

## 0.2.0-beta.4

- Added marker clustering, marker-label modes, marker-size controls, and adjustable opacity for found markers.
- Moved language selection into a dedicated settings window.
- Removed redundant follow-player and automatic-rerouting settings; follow mode remains on the map toolbar and active routes now update automatically.
- Improved selected-marker focus so catalog markers, clusters, cluster icons, and personal markers are dimmed consistently.
- Split Abyss Gates by world layer: high-altitude internal gates are now shown in the Abyss, while surface entrances remain in Pywel.
- Removed the permanent “always show labels” mode and the redundant reset-filters action after usability testing.

## 0.2.0-beta.3

- Added the first display-settings panel with persistent preferences.
- Improved marker readability with selectable sizes, optional hover details, found-marker visibility, and selected-marker highlighting.
- Replaced unsafe nearest-point save matching for chests and display objects with exact evidence-based matching.
- Preserved unmatched scene-object identifiers for future exact catalog links instead of guessing a nearby marker.
- Expanded save-analysis diagnostics and regression coverage.

## 0.2.0-beta.2

- Added read-only automatic completion detection from the newest local `save.save` file.
- Added exact completion matching for supported quests, discoveries, chests, weapon displays, and hidden items.
- Extended Crimson Route integration so requested routes can also appear on the in-game minimap, world map, and world navigation overlay.
- Added compatibility handling for the newer Crimson Desert game build and fixed the packaged Cython scanner byte-buffer type failure.

## 0.2.0-beta.1

- Added a separate compact navigation window with the current player, route, and destination marker.
- Fixed the main-window hotkey immediately reopening the window after it was hidden.
- Prevented the always-on-top window refresh from closing open language menus.
- Added Korean, Simplified Chinese, Traditional Chinese, and Portuguese interface and marker-name translations.
- Updated Pywel trading posts from the public MapGenie dataset and renamed the untranslated `Inn` type to `Tavern`.
- Restored corrected Abyss island overlays and added a Nexus-friendly unpacked archive.

## 0.1.0-beta.4

- Added optional Crimson Route route building, alternatives, automatic rerouting, arrival detection, and route clearing.
- Fixed disappearing individual markers at maximum zoom.
- Refreshed and deduplicated the marker catalog and removed invalid low-altitude Abyss entries.
- Replaced internal localization identifiers with readable marker names.
- Corrected a verified generic shop marker to a trading post.
- Added hover details with marker name, category, and coordinates.
- Added the `Ctrl+Shift+A` main-window hotkey and `Ctrl+Shift+N` navigation-window hotkey.
- Fixed portable startup when `ELECTRON_RUN_AS_NODE` is present and improved packaged Crimson Route error reporting.

## 0.1.0-beta.1–beta.3

- Initial private beta development of the local Pywel and Abyss maps.
- Added live player tracking, searchable catalog markers, personal waypoints, local calibration, and user-confirmed teleporting.
- Added the standalone Electron application, Python game service, and Setup/Portable release pipeline.
