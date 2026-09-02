# Crimson Atlas

Crimson Atlas is an unofficial local interactive companion map for **Crimson Desert**.
It provides live player tracking, Pywel and Abyss map support, searchable marker
groups, personal markers, found-state tracking, map calibration, an always-on-top
desktop window, and optional user-confirmed teleport commands.

The interface is available in English and Russian. The desktop application uses
Electron and React/TypeScript; the local game service is written in Python.

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
