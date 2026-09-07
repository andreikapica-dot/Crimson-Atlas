import os
from pathlib import Path

from services.save_completion import extract_completion_packet, find_latest_save


def test_extracts_only_completed_quests_and_exact_completed_treasure_positions() -> None:
    objects = [
        {
            "__pycr_type__": "QuestSaveData",
            "_questStateList": [
                {"_questKey": 100, "_state": 5, "_completedTime": 123},
                {"_questKey": 200, "_state": 2},
            ],
            "_missionStateList": [
                {"_key": 1001278, "_state": 5},
                {"_key": 1002692, "_state": 2},
            ],
        },
        {
            "__pycr_type__": "KnowledgeSaveData",
            "_list": [{"_key": 300}, {"_key": 100}, {"_key": 300}],
        },
        {
            "__pycr_type__": "DiscoveredLevelGimmickSceneObjectSaveData",
            "_discoveredLevelGimmickSceneObjectSaveDataList": [
                {
                    "_levelGimmickSceneObjectInfoKey": 1000007,
                    "_sceneObjectUuid": [11, 22, 33, 0],
                    "_isCompleted": True,
                },
                {
                    "_levelGimmickSceneObjectInfoKey": 1000007,
                    "_sceneObjectUuid": [44, 55, 66, 0],
                    "_isCompleted": False,
                },
                {
                    "_levelGimmickSceneObjectInfoKey": 1000121,
                    "_sceneObjectUuid": [77, 88, 99, 0],
                    "_fogPivotPosition": [10139.864, -615.942, 4705.406],
                },
                {
                    "_levelGimmickSceneObjectInfoKey": 1000043,
                    "_sceneObjectUuid": [111, 222, 333, 0],
                    "_fogPivotPosition": [8.25, 0, -3.5],
                },
            ],
        },
        {
            "__pycr_type__": "FieldSaveData",
            "_fieldGimmickSaveDataList": [
                {
                    "_levelOriginSceneObjectUuid": [11, 22, 33, 1],
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9000, 650, -3000],
                },
                {
                    "_fieldSaveDataReason": 1,
                    "_gimmickInfoKey": 1004255,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9100, 651, -3100],
                },
                {
                    "_fieldSaveDataReason": 4,
                    "_spawnStyle": 16,
                    "_gimmickInfoKey": 1008984,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9200, 652, -3200],
                },
                {
                    "_fieldSaveDataReason": 1,
                    "_gimmickInfoKey": 9999999,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9300, 653, -3300],
                },
                {
                    "_fieldSaveDataReason": 1,
                    "_gimmickInfoKey": 3020001,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9400, 654, -3400],
                },
                {
                    "_fieldSaveDataReason": 4,
                    "_spawnStyle": 16,
                    "_gimmickInfoKey": 16050007,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9500, 655, -3500],
                },
                {
                    "_fieldSaveDataReason": 4,
                    "_spawnReason": 3776234579,
                    "_spawnStyle": 16,
                    "_gimmickInfoKey": 1002070,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9600, 656, -3600],
                },
                {
                    # Same gimmick but not the proven spawn reason.
                    "_fieldSaveDataReason": 4,
                    "_spawnReason": 123,
                    "_spawnStyle": 16,
                    "_gimmickInfoKey": 1002070,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9700, 657, -3700],
                },
                {
                    "_fieldSaveDataReason": 4,
                    "_spawnStyle": 16,
                    "_gimmickInfoKey": 1002177,
                    "_originSpawnTransform": [1, 1, 1, 0, 0, 0, 1, -9800, 658, -3800],
                },
            ],
        },
    ]

    packet = extract_completion_packet(objects)

    assert packet["completedQuestKeys"] == [100]
    assert packet["completedMissionKeys"] == [1001278]
    assert packet["completedMissionCount"] == 1
    assert packet["completedKnowledgeKeys"] == [100, 300]
    assert packet["learnedKnowledgeCount"] == 2
    assert packet["completedSceneObjectCount"] == 1
    assert packet["completedSceneObjectUuids"] == [[11, 22, 33]]
    assert packet["discoveredLocationCount"] == 1
    assert packet["discoveredLocations"] == [
        {
            "x": -10139.864,
            "y": 615.942,
            "z": -4705.406,
            "realm": "pywel",
            "markerTypes": ["crafting_anvil"],
            "maxDistance": 3.0,
        }
    ]
    assert packet["completedLocations"] == [
        {
            "x": -9100.0,
            "y": 651.0,
            "z": -3100.0,
            "realm": "pywel",
            "markerTypes": ["sealed_artifact"],
            "matchMode": "exact",
        },
        {
            "x": -9200.0,
            "y": 652.0,
            "z": -3200.0,
            "realm": "pywel",
            "markerTypes": ["treasure_box"],
            "matchMode": "exact",
        },
        {
            "x": -9400.0,
            "y": 654.0,
            "z": -3400.0,
            "realm": "pywel",
            "markerTypes": ["weapon_display"],
            "matchMode": "exact",
        },
        {
            "x": -9500.0,
            "y": 655.0,
            "z": -3500.0,
            "realm": "pywel",
            "markerTypes": ["treasure_box"],
            "matchMode": "exact",
        },
        {
            "x": -9600.0,
            "y": 656.0,
            "z": -3600.0,
            "realm": "pywel",
            "markerTypes": ["treasure_box"],
            "matchMode": "exact",
        },
        {
            "x": -9800.0,
            "y": 658.0,
            "z": -3800.0,
            "realm": "pywel",
            "markerTypes": ["treasure_box"],
            "matchMode": "exact",
        },
    ]


def test_find_latest_save_selects_newest_slot(tmp_path: Path) -> None:
    older = tmp_path / "1" / "slot0" / "save.save"
    newer = tmp_path / "1" / "slot1" / "save.save"
    older.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    base = newer.stat().st_mtime_ns
    os.utime(older, ns=(base - 2_000_000, base - 2_000_000))
    os.utime(newer, ns=(base, base))

    result = find_latest_save(tmp_path)

    assert result is not None
    assert result.path == newer
