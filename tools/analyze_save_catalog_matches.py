"""Compare read-only save positions with the offline marker catalog.

This is a diagnostic tool. It never writes to the save file and deliberately
uses a tight spatial radius so that completion rules can be derived from
evidence instead of broad nearest-marker guesses.
"""

from __future__ import annotations

import collections
import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.save_completion import (
    _uuid_prefix,
    _world_position,
    extract_completion_packet,
    find_latest_save,
    parse_save_bytes,
    read_stable_bytes,
)


CATALOG_PATH = ROOT / "frontend" / "public" / "data" / "marker-catalog.json"


def catalog_markers() -> list[dict[str, Any]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    result: list[dict[str, Any]] = []
    for realm, groups in catalog["realms"].items():
        for group in groups:
            marker_type = catalog["types"][group["type"]]["id"]
            source_id_groups = group.get("sourceIds") or [[] for _ in group["points"]]
            for point, source_ids in zip(group["points"], source_id_groups):
                result.append({
                    "realm": realm,
                    "type": marker_type,
                    "x": point[0],
                    "z": point[2],
                    "sourceIds": source_ids,
                })
    return result


def field_records(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed: dict[tuple[int, int, int], tuple[int, bool]] = {}
    for obj in objects:
        if obj.get("__pycr_type__") != "DiscoveredLevelGimmickSceneObjectSaveData":
            continue
        for item in obj.get("_discoveredLevelGimmickSceneObjectSaveDataList") or []:
            prefix = _uuid_prefix(item.get("_sceneObjectUuid"))
            if prefix:
                completed[prefix] = (
                    int(item.get("_levelGimmickSceneObjectInfoKey") or 0),
                    item.get("_isCompleted") is True,
                )

    result: list[dict[str, Any]] = []
    for obj in objects:
        if obj.get("__pycr_type__") != "FieldSaveData":
            continue
        for item in obj.get("_fieldGimmickSaveDataList") or []:
            position = _world_position(item)
            if position is None:
                continue
            x, y, z = position
            prefix = _uuid_prefix(item.get("_levelOriginSceneObjectUuid"))
            scene_key, is_completed = completed.get(prefix, (0, False))
            result.append({
                "x": x,
                "y": y,
                "z": z,
                "realm": "abyss" if y >= 1400 else "pywel",
                "gimmick": int(item.get("_gimmickInfoKey") or 0),
                "scene": scene_key,
                "completed": is_completed,
                "alias": str(item.get("_aliasName") or ""),
                "state": int(item.get("_initStateNameHash") or 0),
                "reason": int(item.get("_fieldSaveDataReason") or 0),
                "spawnReason": int(item.get("_spawnReason") or 0),
                "spawnStyle": int(item.get("_spawnStyle") or 0),
                "saveKey": int(item.get("_fieldGimmickSaveDataKey") or 0),
                "itemKey": int((item.get("_item") or {}).get("_itemInfoKey") or 0),
                "owner": str(item.get("_ownerLevelName") or ""),
            })
    return result


def completed_key_sets(objects: list[dict[str, Any]]) -> dict[str, set[int]]:
    result: dict[str, set[int]] = collections.defaultdict(set)
    for obj in objects:
        if obj.get("__pycr_type__") == "QuestSaveData":
            for field, key_name in (
                ("_questStateList", "_questKey"),
                ("_stageStateData", "_key"),
                ("_missionStateList", "_key"),
                ("_questGaugeStateList", "_key"),
            ):
                for item in obj.get(field) or []:
                    if item.get("_state") != 5 and not item.get("_completedTime"):
                        continue
                    try:
                        result[field].add(int(item[key_name]))
                    except (KeyError, TypeError, ValueError):
                        pass
        elif obj.get("__pycr_type__") == "KnowledgeSaveData":
            for item in obj.get("_list") or []:
                try:
                    result["knowledge"].add(int(item["_key"]))
                except (KeyError, TypeError, ValueError):
                    pass
    return result


def thgl_result(save_bytes: bytes) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.th.gl/api/crimson-desert/save",
        data=save_bytes,
        headers={"Content-Type": "application/octet-stream", "User-Agent": "Crimson Atlas diagnostics/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thgl", action="store_true", help="compare with TH.GL's public save endpoint")
    args = parser.parse_args()
    identity = find_latest_save()
    if identity is None:
        raise SystemExit("No save found")
    objects = parse_save_bytes(read_stable_bytes(identity))
    records = field_records(objects)
    markers = catalog_markers()
    cell_size = 10.0
    grid: dict[tuple[str, int, int], list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        grid[(record["realm"], math.floor(record["x"] / cell_size), math.floor(record["z"] / cell_size))].append(record)

    matches: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for marker in markers:
        cx = math.floor(marker["x"] / cell_size)
        cz = math.floor(marker["z"] / cell_size)
        best: tuple[float, dict[str, Any]] | None = None
        for dx in range(-5, 6):
            for dz in range(-5, 6):
                for record in grid.get((marker["realm"], cx + dx, cz + dz), []):
                    distance = math.hypot(marker["x"] - record["x"], marker["z"] - record["z"])
                    if best is None or distance < best[0]:
                        best = distance, record
        if best and best[0] <= 50.0:
            matches.append((best[0], marker, best[1]))

    print(f"Save: {identity.path}")
    print(f"Positioned save records: {len(records)}")
    print(f"Catalog markers within 50m: {len(matches)}")
    completion_types = {
        "collection_chest", "treasure_box", "sealed_artifact", "chest",
        "treasure_chest_level", "puzzle_chest", "weapon_display",
    }
    for radius in (1, 3, 5, 10, 20, 30, 50):
        relevant = [item for item in matches if item[0] <= radius and item[1]["type"] in completion_types]
        print(f"  completion types within {radius:>2}m: {len(relevant)}")
    by_type = collections.Counter(marker["type"] for _, marker, _ in matches)
    print("\nMatches by catalog type:")
    for marker_type, count in by_type.most_common():
        if count >= 2:
            print(f"  {marker_type}: {count}")

    print("\nSave signatures for likely completion types:")
    interesting = {
        "collection_chest", "treasure_box", "chest", "treasure_chest_level",
        "puzzle_chest", "weapon_display", "hidden_item", "abyss_nexus",
        "abyss_cresset", "abyss_gate", "bonfire", "cooking_station",
        "crafting_anvil", "alchemy_station", "sealed_artifact", "teleport_gate",
        "dungeon", "tunnel", "bell", "greymane_shrine", "memory_fragment",
        "housing_move",
    }
    signatures: dict[str, collections.Counter[tuple[int, int, bool]]] = collections.defaultdict(collections.Counter)
    for _, marker, record in matches:
        if marker["type"] in interesting:
            signatures[marker["type"]][(record["gimmick"], record["scene"], record["completed"])] += 1
    for marker_type in sorted(signatures):
        print(f"  {marker_type}: {signatures[marker_type].most_common(12)}")

    packet = extract_completion_packet(objects)
    print("\nCurrent conservative extraction:")
    print({key: len(value) if isinstance(value, list) else value for key, value in packet.items() if key not in {"type", "status"}})

    if args.thgl:
        remote = thgl_result(read_stable_bytes(identity))
        selected_ids = {
            source_id
            for node_ids in remote.get("nodeIdsByCategory", {}).values()
            for source_id in node_ids
        }
        selected_positions: set[tuple[str, float, float]] = set()
        # The save endpoint uses both X:Z and Z:X identifiers depending on
        # the source table. FieldSaveData itself always exposes game X/Y/Z,
        # so keep a second lookup with the endpoint coordinates reversed.
        selected_record_positions: dict[tuple[float, float], set[str]] = collections.defaultdict(set)
        for category, node_ids in remote.get("nodeIdsByCategory", {}).items():
          for source_id in node_ids:
            prefix, separator, coordinates = source_id.partition("@")
            if not separator:
                continue
            values = coordinates.split(":")
            if len(values) < 2:
                continue
            try:
                selected_positions.add((prefix.split(":", 1)[0], round(float(values[0]), 2), round(float(values[1]), 2)))
                selected_record_positions[(round(float(values[1]), 3), round(float(values[0]), 3))].add(category)
            except ValueError:
                continue
        record_truth = collections.Counter()
        for record in records:
            categories = selected_record_positions.get((round(record["x"], 3), round(record["z"], 3)), set())
            for category in categories:
                record_truth[(
                    category, record["owner"], record["gimmick"], record["reason"],
                    record["spawnReason"], record["spawnStyle"], record["itemKey"],
                )] += 1
        print("\nExact save-record classifications from diagnostic truth:")
        for signature, count in record_truth.most_common(80):
            print(f"  {count:>3} x {signature}")
        exact_completion = [
            (distance, marker, record)
            for distance, marker, record in matches
            if distance <= 1.0 and marker["type"] in completion_types
        ]
        exact_selected = [
            item for item in exact_completion
            if selected_ids.intersection(item[1].get("sourceIds") or [])
            or (
                item[1]["type"],
                round(float(item[1]["x"]), 2),
                round(float(item[1]["z"]), 2),
            ) in selected_positions
            or (
                item[1]["type"],
                round(float(item[1]["z"]), 2),
                round(float(item[1]["x"]), 2),
            ) in selected_positions
        ]
        print("\nExact positioned completion candidates vs TH.GL diagnostic truth:")
        print(f"  candidates={len(exact_completion)}, selected={len(exact_selected)}")
        signatures = collections.Counter(
            (
                record["gimmick"], record["scene"], record["completed"],
                record["reason"], record["spawnReason"], record["spawnStyle"],
                marker["type"],
            )
            for _, marker, record in exact_selected
        )
        for signature, count in signatures.most_common(30):
            print(f"  selected {count:>3} x {signature}")
        false_candidates = [item for item in exact_completion if item not in exact_selected]
        false_signatures = collections.Counter(
            (
                record["gimmick"], record["scene"], record["completed"],
                record["reason"], record["spawnReason"], record["spawnStyle"],
                marker["type"],
            )
            for _, marker, record in false_candidates
        )
        for signature, count in false_signatures.most_common(30):
            print(f"  other    {count:>3} x {signature}")
        key_sets = completed_key_sets(objects)
        all_quest_keys = set().union(*(value for name, value in key_sets.items() if name != "knowledge"))
        for category in ("quests", "knowledge"):
            node_ids = remote.get("nodeIdsByCategory", {}).get(category, [])
            suffixes = {
                int(value.rsplit(":", 1)[1])
                for value in node_ids
                if value.rsplit(":", 1)[-1].isdigit()
            }
            print(f"\nTH.GL {category}: nodes={len(node_ids)}, numeric suffixes={len(suffixes)}")
            print(f"  suffixes in completed quest/stage/mission sets: {len(suffixes & all_quest_keys)}")
            print(f"  suffixes in learned knowledge keys: {len(suffixes & key_sets['knowledge'])}")
            for name, values in key_sets.items():
                print(f"  {name}: keys={len(values)}, overlap={len(suffixes & values)}")

        print("\nTH.GL node coordinate distance to nearest positioned save record:")
        for category, node_ids in remote.get("nodeIdsByCategory", {}).items():
            direct_distances: list[float] = []
            reversed_distances: list[float] = []
            for node_id in node_ids:
                parts = node_id.split("@", 1)
                if len(parts) != 2:
                    continue
                coordinates = parts[1].split(":")
                if len(coordinates) < 2:
                    continue
                try:
                    x, z = float(coordinates[0]), float(coordinates[1])
                except ValueError:
                    continue
                direct_distances.append(min(
                    (math.hypot(x - item["x"], z - item["z"]) for item in records),
                    default=math.inf,
                ))
                reversed_distances.append(min(
                    (math.hypot(z - item["x"], x - item["z"]) for item in records),
                    default=math.inf,
                ))
            direct_distances.sort()
            reversed_distances.sort()
            if not direct_distances:
                continue
            percentile = lambda values, p: values[min(len(values) - 1, int((len(values) - 1) * p))]
            print(
                f"  {category}: coords={len(direct_distances)}, "
                f"direct<=1m={sum(v <= 1 for v in direct_distances)}, "
                f"reversed<=1m={sum(v <= 1 for v in reversed_distances)}, "
                f"direct_p50={percentile(direct_distances, .5):.2f}, "
                f"reversed_p50={percentile(reversed_distances, .5):.2f}"
            )


if __name__ == "__main__":
    main()
