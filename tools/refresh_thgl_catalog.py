"""Refresh the offline marker catalog from the current public TH.GL feeds."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
PAGE_URLS = {
    "thgl.html": "https://crimsondesert.th.gl/maps/Continent%20of%20Pywel",
    "thgl-ru.html": "https://crimsondesert.th.gl/ru/maps/Continent%20of%20Pywel",
}
CDN_ROOT = "https://cdn.th.gl/crimson-desert"


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Crimson Atlas catalog refresh/1.0"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def main() -> None:
    pages: dict[str, bytes] = {}
    for filename, url in PAGE_URLS.items():
        data = download(url)
        pages[filename] = data
        (WORK / filename).write_bytes(data)

    text = pages["thgl.html"].decode("utf-8", errors="replace")
    match = re.search(
        r'nodesPaths\\?":\{\\?"OpenWorld\\?":\\?"([^"\\]+)\\?",\\?"Abyss\\?":\\?"([^"\\]+)',
        text,
    )
    if not match:
        raise RuntimeError("TH.GL page no longer exposes the expected nodesPaths payload")

    for realm, path in zip(("openworld", "abyss"), match.groups(), strict=True):
        payload = download(f"{CDN_ROOT}{path}")
        (WORK / f"thgl-{realm}.raw").write_bytes(payload)

    subprocess.run(
        ["node", str(WORK / "decode_thgl_nodes.mjs")],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_marker_catalog.py")],
        cwd=ROOT,
        check=True,
    )

    catalog = json.loads((ROOT / "frontend/public/data/marker-catalog.json").read_text(encoding="utf-8"))
    print(f"Catalog refreshed: {catalog['markerCount']} visible markers")


if __name__ == "__main__":
    main()
