"""Read-only diagnostic for completion-related Crimson Desert save fields."""

from __future__ import annotations

import argparse
import contextlib
import io
from collections import Counter
from pathlib import Path
from pprint import pformat
from typing import Any

from pycrimson._files import SaveFile
from pycrimson._reflection import ReflectionParser


INTERESTING_TYPES = {
    "ContentsMiscSaveData",
    "FogSaveData",
    "GameEventSaveData",
    "KnowledgeSaveData",
    "QuestSaveData",
    "GameData_GimmickPointData",
    "FieldSaveData",
    "DiscoveredLevelGimmickSceneObjectSaveData",
    "TransformSaveData",
}


def parse_save(path: Path) -> list[dict[str, Any]]:
    """Decrypt and parse a save entirely in memory without modifying it."""
    raw = SaveFile.from_encrypted_file(path)
    temporary = io.BytesIO(raw)
    from bier.EndianedBinaryIO import EndianedBytesIO

    reader = EndianedBytesIO(temporary.getvalue())
    with contextlib.redirect_stdout(io.StringIO()):
        return ReflectionParser(reader).objects


def describe(value: Any, depth: int = 0) -> Any:
    """Return a small structural sample suitable for terminal diagnostics."""
    if depth >= 3:
        return f"<{type(value).__name__}>"
    if isinstance(value, dict):
        return {key: describe(item, depth + 1) for key, item in list(value.items())[:12]}
    if isinstance(value, list):
        return {
            "length": len(value),
            "sample": [describe(item, depth + 1) for item in value[:3]],
        }
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    return value


def collect_field_names(value: Any, result: Counter[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            result[key] += 1
            collect_field_names(item, result)
    elif isinstance(value, list):
        for item in value:
            collect_field_names(item, result)


def find_containers(value: Any, field_name: str, result: list[dict[str, Any]]) -> None:
    """Collect dictionaries that directly contain a requested field."""
    if isinstance(value, dict):
        if field_name in value:
            result.append(value)
        for item in value.values():
            find_containers(item, field_name, result)
    elif isinstance(value, list):
        for item in value:
            find_containers(item, field_name, result)


def focused_container(container: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Keep identity, state, and spatial fields from a large save record."""
    tokens = ("key", "uuid", "complete", "discover", "position", "transform", "location", "field", "world")
    result: dict[str, Any] = {}
    for key, value in container.items():
        if key == "__pycr_type__" or key == field_name or any(token in key.lower() for token in tokens):
            result[key] = describe(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("save", type=Path)
    args = parser.parse_args()

    objects = parse_save(args.save)
    type_counts = Counter(obj.get("__pycr_type__", "unknown") for obj in objects)
    print("Object types:")
    print(pformat(type_counts.most_common()))

    printed_types: Counter[str] = Counter()
    for obj in objects:
        object_type = obj.get("__pycr_type__")
        if object_type in INTERESTING_TYPES:
            limit = 3 if object_type == "GameData_GimmickPointData" else 2 if object_type == "FieldSaveData" else 1
            if printed_types[object_type] >= limit:
                continue
            printed_types[object_type] += 1
            print(f"\n{object_type}:")
            print(pformat(describe(obj), width=120, sort_dicts=False))

    fields: Counter[str] = Counter()
    for obj in objects:
        collect_field_names(obj, fields)
    keywords = ("complete", "collect", "discover", "knowledge", "unlock", "visit", "clear", "acquire")
    matches = [(name, count) for name, count in fields.items() if any(word in name.lower() for word in keywords)]
    print("\nCompletion-related field names:")
    print(pformat(sorted(matches, key=lambda item: (-item[1], item[0])), width=120))

    sample_fields = (
        "_completedSubInnerGimmickUuidList",
        "_isCompleted",
        "_discoveredLevelGimmickSceneObjectSaveDataList",
    )
    for field_name in sample_fields:
        containers: list[dict[str, Any]] = []
        for obj in objects:
            find_containers(obj, field_name, containers)
        print(f"\nContainers with {field_name}: {len(containers)}")
        for container in containers[:5]:
            print(pformat(focused_container(container, field_name), width=160, sort_dicts=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
