"""Read-only Crimson Desert save progress monitoring.

Only progress evidence that can be mapped without guessing is emitted:
completed quest keys, completed objects, and discovered facilities with a
proven absolute world position. The game save is never opened for writing.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from bier.EndianedBinaryIO import EndianedBytesIO
from pycrimson._files import SaveFile
from pycrimson._reflection import ReflectionParser


log = logging.getLogger(__name__)

COMPLETED_STATE = 5
TREASURE_SCENE_INFO_KEY = 1000007

# Level discovery records sometimes carry an absolute fog pivot.  These keys
# describe stable map facilities whose catalog type is known from the installed
# LevelGimmickSceneObjectInfo table.  Sector-local pivots are intentionally not
# emitted: without the owning sector transform they are not world coordinates.
DISCOVERED_SCENE_MARKER_TYPES: dict[int, tuple[str, ...]] = {
    1000043: ("bonfire",),
    1000044: ("bonfire",),
    1000054: ("grindstone", "mine_blacksmith"),
    1000107: ("cooking_station",),
    1000121: ("crafting_anvil",),
}

# These signatures were verified against both the current save structure and
# the map completion result.  A FieldGimmick record with one of these exact
# signatures is created only after the corresponding collectible is consumed.
# Keep this list deliberately small: guessing from a nearby generic gimmick
# produces false positives in towns and dense treasure areas.
COMPLETED_GIMMICK_TYPES: dict[tuple[int, int, int], tuple[str, ...]] = {
    (1004255, 1, 0): ("sealed_artifact",),
    (1008984, 4, 16): ("treasure_box",),
    # Exact consumed-object signatures validated against the current save
    # format. Keep the marker type narrow: several neighbouring records use
    # the same reason/style but represent unrelated world gimmicks.
    (3020001, 1, 0): ("weapon_display",),
    (1000071, 1, 0): ("weapon_display",),
    (1000072, 1, 0): ("weapon_display",),
    (16050001, 4, 16): ("treasure_box",),
    (16050005, 4, 16): ("treasure_box",),
    (16050006, 4, 16): ("treasure_box",),
    (16050006, 6, 16): ("treasure_box",),
    (16050007, 4, 16): ("treasure_box",),
    (1005586, 4, 16): ("treasure_box",),
}

# Some completion records need the spawn-reason hash to distinguish the real
# collectible from other instances of the same gimmick.  These rules were
# checked against five local save snapshots. The rule identifies what kind of
# consumed object a record represents; the frontend still requires exact
# coordinate identity and will not substitute a nearby catalog pin.
COMPLETED_GIMMICK_RULES: dict[tuple[int, int, int, int], tuple[str, ...]] = {
    (1002177, 4, 0, 16): ("treasure_box",),
    (1002070, 4, 3776234579, 16): ("treasure_box",),
    (1002124, 4, 3809551542, 16): ("treasure_box",),
    (16070018, 6, 0, 16): ("treasure_chest_level",),
    (18020015, 6, 0, 15): ("weapon_display",),
}


@dataclass(frozen=True)
class SaveIdentity:
    path: Path
    modified_ns: int
    size: int


def default_save_root() -> Path:
    """Return Pearl Abyss' official local PC save directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Pearl Abyss" / "CD" / "save"
    return Path.home() / "AppData" / "Local" / "Pearl Abyss" / "CD" / "save"


def find_latest_save(root: Path | None = None) -> SaveIdentity | None:
    """Find the newest normal save slot across local user profiles."""
    save_root = root or default_save_root()
    candidates: list[SaveIdentity] = []
    if not save_root.is_dir():
        return None
    for path in save_root.glob("*/slot*/save.save"):
        try:
            stat = path.stat()
        except OSError:
            continue
        candidates.append(SaveIdentity(path, stat.st_mtime_ns, stat.st_size))
    return max(candidates, key=lambda item: item.modified_ns, default=None)


def read_stable_bytes(identity: SaveIdentity) -> bytes:
    """Read a save only when it did not change during the read."""
    before = identity.path.stat()
    data = identity.path.read_bytes()
    after = identity.path.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise RuntimeError("Save changed while it was being read")
    if (after.st_mtime_ns, after.st_size) != (identity.modified_ns, identity.size):
        raise RuntimeError("Save changed before it could be read")
    return data


def parse_save_bytes(encrypted: bytes) -> list[dict[str, Any]]:
    """Decrypt and deserialize a save entirely in memory."""
    decrypted = SaveFile.from_encrypted(EndianedBytesIO(encrypted))
    with contextlib.redirect_stdout(io.StringIO()):
        return ReflectionParser(EndianedBytesIO(decrypted)).objects


def _uuid_prefix(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, list) or len(value) < 3:
        return None
    try:
        return int(value[0]), int(value[1]), int(value[2])
    except (TypeError, ValueError):
        return None


def _world_position(record: dict[str, Any]) -> tuple[float, float, float] | None:
    transform = record.get("_originSpawnTransform") or record.get("_transform")
    if not isinstance(transform, (list, tuple)) or len(transform) < 10:
        return None
    try:
        return float(transform[-3]), float(transform[-2]), float(transform[-1])
    except (TypeError, ValueError):
        return None


def _absolute_fog_position(record: dict[str, Any]) -> tuple[float, float, float] | None:
    """Convert a proven absolute fog pivot to Atlas world coordinates.

    Pywel level data stores the axes with the opposite sign. Small pivots are
    local offsets inside a sector or Abyss island and cannot be placed safely
    until that parent transform is known.
    """
    pivot = record.get("_fogPivotPosition")
    if not isinstance(pivot, (list, tuple)) or len(pivot) < 3:
        return None
    try:
        px, py, pz = (float(pivot[0]), float(pivot[1]), float(pivot[2]))
    except (TypeError, ValueError):
        return None
    if max(abs(px), abs(pz)) < 1000.0:
        return None
    return -px, -py, -pz


def extract_completion_packet(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Extract exact, catalog-mappable completion evidence from parsed objects."""
    object_list = list(objects)
    quest_keys: set[int] = set()
    mission_keys: set[int] = set()
    learned_knowledge_keys: set[int] = set()
    completed_scene_uuids: set[tuple[int, int, int]] = set()
    discovered_locations: dict[tuple[float, float, float], dict[str, Any]] = {}

    for obj in object_list:
        object_type = obj.get("__pycr_type__")
        if object_type == "QuestSaveData":
            for quest in obj.get("_questStateList") or []:
                if quest.get("_state") == COMPLETED_STATE and quest.get("_completedTime"):
                    try:
                        quest_keys.add(int(quest["_questKey"]))
                    except (KeyError, TypeError, ValueError):
                        continue
            for mission in obj.get("_missionStateList") or []:
                if mission.get("_state") != COMPLETED_STATE:
                    continue
                try:
                    mission_keys.add(int(mission["_key"]))
                except (KeyError, TypeError, ValueError):
                    continue
        elif object_type == "KnowledgeSaveData":
            for knowledge in obj.get("_list") or []:
                try:
                    learned_knowledge_keys.add(int(knowledge["_key"]))
                except (KeyError, TypeError, ValueError):
                    continue
        elif object_type == "DiscoveredLevelGimmickSceneObjectSaveData":
            for scene in obj.get("_discoveredLevelGimmickSceneObjectSaveDataList") or []:
                try:
                    scene_info_key = int(scene.get("_levelGimmickSceneObjectInfoKey") or 0)
                except (TypeError, ValueError):
                    scene_info_key = 0
                marker_types = DISCOVERED_SCENE_MARKER_TYPES.get(scene_info_key)
                position = _absolute_fog_position(scene)
                if marker_types is not None and position is not None:
                    x, y, z = position
                    discovered_locations[position] = {
                        "x": round(x, 3),
                        "y": round(y, 3),
                        "z": round(z, 3),
                        "realm": "pywel",
                        "markerTypes": list(marker_types),
                        "maxDistance": 3.0,
                    }
                if scene.get("_isCompleted") is not True:
                    continue
                # Key 1000007 is a completed treasure container. Other scene
                # types remain telemetry-only until their catalog identity is proven.
                if scene.get("_levelGimmickSceneObjectInfoKey") != TREASURE_SCENE_INFO_KEY:
                    continue
                prefix = _uuid_prefix(scene.get("_sceneObjectUuid"))
                if prefix:
                    completed_scene_uuids.add(prefix)

    locations: dict[tuple[float, float, float], dict[str, Any]] = {}
    for obj in object_list:
        if obj.get("__pycr_type__") != "FieldSaveData":
            continue
        # A completed scene UUID proves that its root object was consumed, but
        # its transform is not necessarily the published catalog pin. Some
        # chest pins represent a cave entrance or a group centre hundreds of
        # metres away. Keep UUIDs as exact identity evidence and never turn
        # them into a nearest-marker guess here.
        for record in obj.get("_fieldGimmickSaveDataList") or []:
            try:
                signature = (
                    int(record.get("_gimmickInfoKey") or 0),
                    int(record.get("_fieldSaveDataReason") or 0),
                    int(record.get("_spawnStyle") or 0),
                )
                precise_signature = (
                    signature[0],
                    signature[1],
                    int(record.get("_spawnReason") or 0),
                    signature[2],
                )
            except (TypeError, ValueError):
                continue
            precise_rule = COMPLETED_GIMMICK_RULES.get(precise_signature)
            if precise_rule is not None:
                marker_types = precise_rule
            else:
                marker_types = COMPLETED_GIMMICK_TYPES.get(signature)
            if marker_types is None:
                continue
            position = _world_position(record)
            if position is None:
                continue
            x, y, z = position
            locations[position] = {
                "x": round(x, 3),
                "y": round(y, 3),
                "z": round(z, 3),
                "realm": "abyss" if y >= 1400.0 else "pywel",
                "markerTypes": list(marker_types),
                "matchMode": "exact",
            }

    return {
        "type": "save_completion",
        "status": "ready",
        "completedQuestKeys": sorted(quest_keys),
        "completedMissionKeys": sorted(mission_keys),
        "completedKnowledgeKeys": sorted(learned_knowledge_keys),
        "completedSceneObjectUuids": [list(value) for value in sorted(completed_scene_uuids)],
        "completedLocations": list(locations.values()),
        "discoveredLocations": list(discovered_locations.values()),
        "completedQuestCount": len(quest_keys),
        "completedMissionCount": len(mission_keys),
        "completedSceneObjectCount": len(completed_scene_uuids),
        "matchedLocationCount": len(locations),
        "discoveredLocationCount": len(discovered_locations),
        "learnedKnowledgeCount": len(learned_knowledge_keys),
    }


class SaveCompletionMonitor:
    """Poll save metadata cheaply and parse only after the save changes."""

    def __init__(
        self,
        callback: Callable[[dict[str, Any]], None],
        *,
        root: Path | None = None,
        interval: float = 15.0,
    ) -> None:
        self._callback = callback
        self._root = root
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_identity: SaveIdentity | None = None
        self.latest_packet: dict[str, Any] = {
            "type": "save_completion",
            "status": "waiting",
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="save-completion", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def scan_once(self) -> dict[str, Any] | None:
        identity = find_latest_save(self._root)
        if identity is None:
            packet = {"type": "save_completion", "status": "not_found"}
            self.latest_packet = packet
            return packet
        if identity == self._last_identity:
            return None
        objects = parse_save_bytes(read_stable_bytes(identity))
        packet = extract_completion_packet(objects)
        packet["saveSlot"] = identity.path.parent.name
        packet["saveModifiedNs"] = identity.modified_ns
        self._last_identity = identity
        self.latest_packet = packet
        return packet

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                packet = self.scan_once()
                if packet is not None:
                    self._callback(packet)
                    if packet.get("status") == "ready":
                        log.info(
                            "Save completion loaded: %d quests, %d completed and %d discovered locations",
                            packet["completedQuestCount"],
                            packet["matchedLocationCount"],
                            packet["discoveredLocationCount"],
                        )
            except Exception as exc:
                log.warning("Could not read save completion: %s", exc)
                packet = {
                    "type": "save_completion",
                    "status": "error",
                    "error": str(exc),
                }
                self.latest_packet = packet
                self._callback(packet)
            self._stop.wait(self._interval)
