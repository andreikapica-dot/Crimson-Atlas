# Crimson Atlas

Crimson Atlas is an unofficial local interactive companion map for **Crimson Desert**.
It provides live player tracking, Pywel and Abyss map support, searchable marker
groups, personal markers, found-state tracking, map calibration, an always-on-top
desktop window, and optional user-confirmed teleport commands.

The interface is available in English, Russian, Korean, Simplified Chinese,
Traditional Chinese, and Portuguese. The desktop application uses Electron and
React/TypeScript; the local game service is written in Python.

Current beta features also include:

- a dedicated settings window with marker size, clustering, label, visibility,
  focus, and found-marker opacity controls;
- a compact navigation window and optional Crimson Route 6.9.4+ integration;
- route display in Atlas and, through Crimson Route, on the in-game minimap,
  world map, and navigation overlay;
- read-only completion detection from the newest local save file, using exact
  catalog links rather than nearest-marker guesses.

See [CHANGELOG.md](CHANGELOG.md) for the version-by-version history.

## Source-only repository

This repository contains the application source code, tests, development tools,
and release scripts. It intentionally does **not** contain:

- proprietary or third-party map tiles;
- marker databases and guide content;
- extracted game assets or diagnostic dumps;
- packaged executables, build output, logs, or local configuration;
- the maintainer's private `.env` files.

As a result, a checkout can be inspected and tested, but a complete distributable
build also requires the separately maintained local map and catalog assets.

## Development

Requirements:

- Windows 10 or Windows 11
- Python 3.12+
- Node.js 20+

Frontend checks:

```powershell
cd frontend
npm install
npm test -- --run
npm run build
```

Python checks:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

## Important notice

Crimson Atlas is an unofficial fan-made project and is not affiliated with,
endorsed by, or sponsored by Pearl Abyss. Crimson Desert and related names and
assets belong to their respective owners.

The software reads data from a running game process and can perform an explicitly
requested teleport operation. Compatibility can change after game updates.

## Copyright and use

Copyright © 2026 Andrei. All rights reserved.

The source is published for viewing and security review. **No license is granted**
to copy, modify, redistribute, sublicense, or sell this code. No `LICENSE` file is
provided.

## Support

- [Donatello](https://donatello.to/andreikapica)
- [Ko-fi](https://ko-fi.com/andrei33721)
