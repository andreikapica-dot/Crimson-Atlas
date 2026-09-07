import json
from pathlib import Path

import pytest

from tools.build_marker_catalog import ABYSS_MIN_HEIGHT, POINT_TYPE_OVERRIDES, display_name, group_for


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "frontend" / "public" / "data" / "marker-catalog.json"


def load_built_catalog() -> dict:
    if not CATALOG_PATH.exists():
        pytest.skip("The source-only repository does not include the private built marker catalog")
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_internal_translation_reference_is_never_user_visible() -> None:
    localized = {"hi_common_axe_mace": "@hjeglx"}
    assert display_name("hi_common_axe_mace", localized, localized, "ru") == "Обычный топор или булава"


def test_hidden_items_are_treasure_markers() -> None:
    assert group_for("hi_epic_axe_mace") == "treasures"


def test_abyss_height_cutoff_excludes_surface_layer() -> None:
    assert 637.92 < ABYSS_MIN_HEIGHT < 1797.0


def test_built_abyss_catalog_contains_only_the_upper_world_layer() -> None:
    catalog = load_built_catalog()
    points = [
        point
        for marker_group in catalog["realms"]["abyss"]
        for point in marker_group["points"]
    ]

    assert points
    assert min(point[1] for point in points) >= ABYSS_MIN_HEIGHT


def test_abyss_gates_are_split_by_world_layer() -> None:
    catalog = load_built_catalog()
    gate_type = next(index for index, item in enumerate(catalog["types"]) if item["id"] == "abyss_gate")
    pywel_group = next(group for group in catalog["realms"]["pywel"] if group["type"] == gate_type)
    abyss_group = next(group for group in catalog["realms"]["abyss"] if group["type"] == gate_type)

    assert len(pywel_group["points"]) == 10
    assert len(abyss_group["points"]) == 30
    assert max(point[1] for point in pywel_group["points"]) < ABYSS_MIN_HEIGHT
    assert min(point[1] for point in abyss_group["points"]) >= ABYSS_MIN_HEIGHT


def test_reported_surface_chest_is_not_in_built_abyss_catalog() -> None:
    catalog = load_built_catalog()
    points = [
        point
        for marker_group in catalog["realms"]["abyss"]
        for point in marker_group["points"]
    ]

    assert not any(
        abs(point[0] - -11114.77) < 0.01
        and abs(point[1] - 556.178) < 0.01
        and abs(point[2] - -4481.855) < 0.01
        for point in points
    )


def test_verified_trading_post_is_not_labeled_as_generic_shop() -> None:
    assert POINT_TYPE_OVERRIDES[("pywel", "shop", -11219.027, -6663.361)] == "trading_post"


def test_catalog_preserves_source_ids_for_save_completion_matching() -> None:
    catalog = load_built_catalog()
    for realm_groups in catalog["realms"].values():
        for group in realm_groups:
            if "sourceIds" in group:
                assert len(group["sourceIds"]) == len(group["points"])

    main_quest_index = next(index for index, item in enumerate(catalog["types"]) if item["id"] == "main_quest")
    main_quest_group = next(group for group in catalog["realms"]["pywel"] if group["type"] == main_quest_index)
    assert any(
        source_id.startswith("main_quest@")
        for source_ids in main_quest_group["sourceIds"]
        for source_id in source_ids
    )
