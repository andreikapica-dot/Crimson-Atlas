"""Download the public zoom 5-6 TH.GL tile levels for offline use."""

from __future__ import annotations

import concurrent.futures
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MAPS = ROOT / "frontend" / "public" / "maps"
MAPS = {
    "pywel": "https://cdn.th.gl/crimson-desert/map-tiles/OpenWorld-25391853dd739b8fd7d28d6280f02d15/{z}/{y}/{x}.webp",
    "abyss": "https://cdn.th.gl/crimson-desert/map-tiles/Abyss-977eb3908409067c108beead55c7a945/{z}/{y}/{x}.webp",
}


def fetch(task: tuple[str, str, int, int, int]) -> tuple[str, bool, int]:
    realm, template, zoom, row, column = task
    target = PUBLIC_MAPS / realm / str(zoom) / str(row) / f"{column}.webp"
    if target.exists() and target.stat().st_size > 0:
        return realm, True, target.stat().st_size
    request = urllib.request.Request(
        template.format(z=zoom, y=row, x=column),
        headers={"User-Agent": "Crimson Atlas offline map updater"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return realm, False, 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return realm, True, len(data)


def main() -> None:
    tasks = []
    for realm, template in MAPS.items():
        for zoom in (5, 6):
            size = 2**zoom
            tasks.extend((realm, template, zoom, row, column) for row in range(size) for column in range(size))
    totals = {realm: {"files": 0, "bytes": 0, "missing": 0} for realm in MAPS}
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        for index, (realm, ok, byte_count) in enumerate(pool.map(fetch, tasks), 1):
            totals[realm]["files" if ok else "missing"] += 1
            totals[realm]["bytes"] += byte_count
            if index % 1000 == 0:
                print(f"Processed {index}/{len(tasks)} tiles")
    for realm, total in totals.items():
        print(f"{realm}: {total['files']} files, {total['bytes'] / 1024 / 1024:.1f} MiB, {total['missing']} missing")


if __name__ == "__main__":
    main()
