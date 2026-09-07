"""Build offline marker-name translations for every catalog type.

The generated cache is consumed by build_marker_catalog.py. The application
never calls an online translation service at runtime.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
CATALOG = ROOT / "frontend" / "public" / "data" / "marker-catalog.json"
CACHE = WORK / "marker-name-translations.json"
TARGETS = {"ko": "ko", "zh-CN": "zh-CN", "zh-TW": "zh-TW", "pt": "pt"}


def translate_text(text: str, target: str) -> str:
    query = urllib.parse.urlencode({
        "client": "gtx", "sl": "en", "tl": target, "dt": "t", "q": text,
    })
    request = urllib.request.Request(
        f"https://translate.googleapis.com/translate_a/single?{query}",
        headers={"User-Agent": "Crimson Atlas offline localization builder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in payload[0] if part and part[0]).strip()


def translate_batch(values: list[str], target: str) -> list[str]:
    translated = translate_text("\n".join(values), target).splitlines()
    if len(translated) == len(values) and all(item.strip() for item in translated):
        return [item.strip() for item in translated]
    return [translate_text(value, target) for value in values]


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    marker_types = catalog["types"]

    for language, target in TARGETS.items():
        pending = [item for item in marker_types if not cache.get(item["id"], {}).get(language)]
        for offset in range(0, len(pending), 35):
            batch = pending[offset : offset + 35]
            results = translate_batch([item["nameEn"] for item in batch], target)
            for item, translated in zip(batch, results, strict=True):
                cache.setdefault(item["id"], {})[language] = translated
            print(f"{language}: {min(offset + len(batch), len(pending))}/{len(pending)}", flush=True)
            time.sleep(0.08)

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for item in marker_types:
        item["translations"] = {
            "ru": item["name"],
            "en": item["nameEn"],
            **cache.get(item["id"], {}),
        }
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Translated {len(marker_types)} marker types into {len(TARGETS)} languages")


if __name__ == "__main__":
    main()
