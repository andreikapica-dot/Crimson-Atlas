"""Build the offline Crimson Atlas marker catalog from public TH.GL node data."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
PUBLIC = ROOT / "frontend" / "public"
ICON_SOURCE = Path(r"D:\Projects\icons")
ICON_OUTPUT = PUBLIC / "marker-icons"

# The Abyss node feed also contains surface-world objects that share X/Z with
# the floating islands. Real Abyss stages extracted from the game are centred
# at Y 1797..2516; the low layer (usually Y 350..1100) is Pywel data and must
# not be shown on the Abyss map.
ABYSS_MIN_HEIGHT = 1400.0

EXACT_NAMES = {
    "ru": {
        "trading_post": "Торговый пост",
        "art_shop": "Магазин предметов искусства",
        "equipment_shop": "Магазин снаряжения",
        "weapon_shop": "Оружейный магазин",
        "inn": "Таверна",
        "hi_common_axe_mace": "Обычный топор или булава",
        "hi_uncommon_axe_mace": "Необычный топор или булава",
        "hi_rare_axe_mace": "Редкий топор или булава",
        "hi_epic_axe_mace": "Эпический топор или булава",
        "hi_legendary_axe_mace": "Легендарный топор или булава",
    },
    "en": {
        "inn": "Tavern",
        "hi_common_axe_mace": "Common Axe or Mace",
        "hi_uncommon_axe_mace": "Uncommon Axe or Mace",
        "hi_rare_axe_mace": "Rare Axe or Mace",
        "hi_epic_axe_mace": "Epic Axe or Mace",
        "hi_legendary_axe_mace": "Legendary Axe or Mace",
    },
}

# Public MapGenie Pywel category 15068 (Trading Center), refreshed 2026-09-04.
# Coordinates are projected into the Atlas game-coordinate plane using the
# same registered affine transform as tools/build_mapgenie_pywel_tiles.py.
MAPGENIE_TRADING_CENTERS = [
    (-10670.266, -3732.843), (-3599.834, 3538.854), (-4445.289, 2337.621),
    (-6126.020, -1014.233), (-4383.038, -4284.887), (-4281.237, -4062.272),
    (-6991.153, -3879.822), (-4952.873, -4254.264), (-8791.076, -2869.652),
    (-10018.549, -4687.023), (-8029.554, -3250.102), (-6773.384, -3354.538),
    (-7887.075, -2703.313), (-6847.667, -2983.589), (-5665.647, -1836.932),
    (-5360.563, -5303.227), (-6639.815, 244.742), (-11215.284, -6668.041),
    (-8726.880, -2090.552), (-11775.176, -2363.478), (-6481.238, -1088.349),
    (-6179.595, -510.312), (-7175.846, -871.465), (-9972.413, -1266.585),
    (-10657.468, -4948.297), (-8075.396, -3604.664), (-8209.080, -1740.963),
    (-6028.878, -1657.530), (-9696.995, -2601.898), (-9452.303, -5125.662),
    (-5755.394, -2040.368), (-9830.830, -1995.253), (-4533.066, -4775.364),
    (-8279.127, -566.045), (-8033.184, -664.248), (-6231.857, -3240.659),
    (-8541.479, -4646.560), (-9386.811, -2101.213), (-9959.092, 1134.810),
    (-7928.762, -2762.568), (-7467.068, -2474.437), (-10620.379, -6078.613),
    (-9270.172, -2738.937), (-11481.912, -1736.898),
]

# Corrections verified against the in-game map. TH.GL currently publishes
# these individual locations under a broader type than the game UI does.
POINT_TYPE_OVERRIDES = {
    ("pywel", "shop", -11219.027, -6663.361): "trading_post",
}

GROUPS = [
    {"id": "travel", "label": "Путешествия и места", "color": "#62b4e8", "icon": "point-of-interest.png"},
    {"id": "quests", "label": "Задания", "color": "#f0c45d", "icon": "main-quest.png"},
    {"id": "treasures", "label": "Сокровища и коллекции", "color": "#dca85b", "icon": "treasure-chest.png"},
    {"id": "abyss", "label": "Бездна", "color": "#b989e6", "icon": "abyss-cresset.png"},
    {"id": "ores", "label": "Руды и минералы", "color": "#9fa8b2", "icon": "pickaxe.png"},
    {"id": "plants", "label": "Растения и сбор", "color": "#72c98d", "icon": "plants.png"},
    {"id": "animals", "label": "Животные и рыбалка", "color": "#8fc47b", "icon": "animals.png"},
    {"id": "shops", "label": "Торговцы и услуги", "color": "#df9d65", "icon": "money.png"},
    {"id": "crafting", "label": "Ремесло и рецепты", "color": "#76b7aa", "icon": "crafting-tools.png"},
    {"id": "combat", "label": "Враги и боссы", "color": "#e16e68", "icon": "enemy.png"},
    {"id": "activities", "label": "Активности", "color": "#e58bc4", "icon": "card-game.png"},
    {"id": "other", "label": "Прочее", "color": "#a8adb5", "icon": "point-of-interest.png"},
]

EXACT_ICONS = {
    "abyss_cresset": "abyss-cresset.png", "abyss_gate": "abyss-gate.png",
    "abyss_nexus": "abyss-nexus.png", "sealed_artifact": "sealed-abyss-artifact.png",
    "bonfire": "bonfire.png", "bell": "bell.png", "cave": "cave.png",
    "watchtower": "tower.png", "ruins": "ruins.png", "village": "village.png",
    "treasure_box": "treasure-chest.png", "treasure_chest_level": "treasure-chest.png",
    "chest": "chest.png", "main_quest": "main-quest.png", "bounty": "bounties.png",
    "mine_iron": "iron-ore.png", "mine_copper": "copper-ore.png", "mine_gold": "gold-ore.png",
    "mine_silver": "silver-ore.png", "mine_diamond": "diamond.png", "mine_ruby": "ruby.png",
    "mine_bismuth": "bismuth-ore.png", "mine_redstone": "garnet.png",
    "mine_greenstone": "epidote.png", "mine_bluestone": "azurite.png",
}


def translations(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    result: dict[str, str] = {}
    pattern = re.compile(r'\\"([^"\\]+)\\":\\"((?:\\\\.|[^"\\])*)\\"')
    for key, encoded in pattern.findall(text):
        try:
            result[key] = json.loads(f'"{encoded}"')
        except json.JSONDecodeError:
            continue
    for _ in range(8):
        changed = False
        for key, value in list(result.items()):
            if value.startswith("@") and value in result:
                replacement = result[value]
                if replacement != value:
                    result[key] = replacement
                    changed = True
        if not changed:
            break
    return result


def display_name(marker_type: str, localized: dict[str, str], english: dict[str, str], language: str) -> str:
    """Return a human-readable name and never expose TH.GL localization keys."""
    fallback = marker_type.replace("_", " ").title()
    value = EXACT_NAMES.get(language, {}).get(marker_type)
    if not value:
        value = localized.get(marker_type) or english.get(marker_type) or fallback
    if value.startswith("@"):
        value = EXACT_NAMES.get(language, {}).get(marker_type) or fallback
    return value


def group_for(marker_type: str) -> str:
    value = marker_type.lower()
    if value.startswith("abyss_") or value in {"sealed_artifact", "faction_node"}:
        return "abyss"
    if "quest" in value or "bounty" in value:
        return "quests"
    if value.startswith("hi_") or any(word in value for word in ("chest", "treasure", "artifact", "collect", "memory_fragment", "legendary", "key_item")):
        return "treasures"
    if value.startswith("mine_") or any(word in value for word in ("mineral", "ore", "quarry")):
        return "ores"
    if value.startswith("gather_") or any(word in value for word in ("leaf", "plant", "flower", "herb", "mushroom", "wood")):
        return "plants"
    if value.startswith(("animal_", "bug_", "fish_", "creature_")) or "fishing" in value:
        return "animals"
    if any(word in value for word in ("shop", "merchant", "vendor", "stable", "warehouse", "bank", "inn", "market", "trading")):
        return "shops"
    if value.startswith(("crafting_", "manual_")) or any(word in value for word in ("recipe", "anvil", "grindstone", "workshop", "dyehouse", "cauldron")):
        return "crafting"
    if any(word in value for word in ("boss", "enemy", "elite", "monster", "combat")):
        return "combat"
    if any(word in value for word in ("contest", "duel", "game", "race", "wrestling", "gambling", "ceelo", "seotda")):
        return "activities"
    if any(word in value for word in ("bonfire", "teleport", "gate", "town", "village", "castle", "camp", "cave", "ruins", "shrine", "temple", "tower", "location", "stronghold", "dock", "station")):
        return "travel"
    return "other"


def icon_for(marker_type: str, group_id: str) -> str:
    if marker_type in EXACT_ICONS:
        return EXACT_ICONS[marker_type]
    group = next(item for item in GROUPS if item["id"] == group_id)
    return group["icon"]


def description_for(marker_type: str, name: str, group_id: str) -> str:
    exact = {
        "faction_quest": "Задание фракции. Цель и условия зависят от фракции, региона и текущего этапа прохождения.",
        "main_quest": "Точка основного задания, связанная с развитием сюжетной линии.",
        "bonfire": "Костёр для отдыха и восстановления. Некоторые костры также используются как ориентиры быстрого перемещения.",
        "abyss_cresset": "Абисс-стела — объект Бездны, связанный с исследованием и открытием её маршрутов.",
        "abyss_gate": "Врата Бездны соединяют отдельные участки и маршруты пространства Бездны.",
        "abyss_nexus": "Средоточие Бездны — важный узел, связанный с перемещением и исследованием Бездны.",
        "sealed_artifact": "Запечатанный артефакт Бездны. Осмотрите окружение: доступ к нему может требовать обходного пути или взаимодействия.",
    }
    if marker_type in exact:
        return exact[marker_type]
    templates = {
        "travel": f"{name} — ориентир или полезное место для исследования мира.",
        "quests": f"{name} — точка задания. Содержание зависит от текущего этапа прохождения.",
        "treasures": f"{name} — тайник или коллекционный объект. Проверьте окружение и возможные скрытые проходы.",
        "abyss": f"{name} — объект, связанный с исследованием и маршрутами Бездны.",
        "ores": f"{name} — месторождение ресурса, доступного для добычи.",
        "plants": f"{name} — место сбора растения или природного материала.",
        "animals": f"{name} — возможное место появления животного, существа или рыбы.",
        "shops": f"{name} — торговая точка или объект обслуживания.",
        "crafting": f"{name} — ремесленный объект, материал или рецепт.",
        "combat": f"{name} — опасная боевая точка. Подготовьтесь перед приближением.",
        "activities": f"{name} — дополнительная активность или мини-игра.",
        "other": f"{name} — дополнительная точка интереса на карте.",
    }
    return templates[group_id]


def main() -> None:
    ru = translations(WORK / "thgl-ru.html")
    en = translations(WORK / "thgl.html")
    translation_cache_path = WORK / "marker-name-translations.json"
    translation_cache = (
        json.loads(translation_cache_path.read_text(encoding="utf-8"))
        if translation_cache_path.exists()
        else {}
    )
    source_groups = {
        "pywel": json.loads((WORK / "thgl-openworld.json").read_text(encoding="utf-8")),
        "abyss": json.loads((WORK / "thgl-abyss.json").read_text(encoding="utf-8")),
    }
    marker_types = sorted(
        {group["type"] for groups in source_groups.values() for group in groups}
        | set(POINT_TYPE_OVERRIDES.values())
    )
    type_index = {marker_type: index for index, marker_type in enumerate(marker_types)}
    types = []
    used_icons = {group["icon"] for group in GROUPS}
    for marker_type in marker_types:
        group_id = group_for(marker_type)
        icon = icon_for(marker_type, group_id)
        used_icons.add(icon)
        name_ru = display_name(marker_type, ru, en, "ru")
        name_en = display_name(marker_type, en, en, "en")
        types.append({
            "id": marker_type,
            "name": name_ru,
            "nameEn": name_en,
            "translations": {
                "ru": name_ru,
                "en": name_en,
                **translation_cache.get(marker_type, {}),
            },
            "description": description_for(marker_type, name_ru, group_id),
            "group": group_id,
            "icon": icon,
        })

    realms: dict[str, list[dict[str, object]]] = {}
    marker_count = 0
    teleport_count = 0
    for realm, groups in source_groups.items():
        # Public node dumps may repeat the same spawn in several payload
        # fragments. Merge by type and exact rounded game position so one
        # in-game object produces one clickable Atlas marker.
        points_by_type: dict[int, list[list[float | None]]] = {}
        source_ids_by_type: dict[int, list[list[str]]] = {}
        seen_points: set[tuple[int, float, float | None, float]] = set()
        point_indices: dict[tuple[int, float, float | None, float], int] = {}
        source_trading_points: list[tuple[float, float | None, float]] = []
        for group in groups:
            for spawn in group.get("spawns", []):
                p = spawn.get("p", [])
                if len(p) < 2:
                    continue
                # TH.GL/Leaflet stores [game Z, game X, game Y].
                raw_height = float(p[2]) if len(p) > 2 else 0.0
                if realm == "abyss" and raw_height < ABYSS_MIN_HEIGHT:
                    continue
                height = round(raw_height, 3) if raw_height != 0 else None
                x = round(float(p[1]), 3)
                z = round(float(p[0]), 3)
                corrected_type = POINT_TYPE_OVERRIDES.get(
                    (realm, group["type"], x, z),
                    group["type"],
                )
                if realm == "pywel" and corrected_type == "trading_post":
                    source_trading_points.append((x, height, z))
                    continue
                type_id = type_index[corrected_type]
                points = points_by_type.setdefault(type_id, [])
                source_ids = source_ids_by_type.setdefault(type_id, [])
                key = (type_id, x, height, z)
                if key in seen_points:
                    source_id = spawn.get("id")
                    if source_id is not None:
                        point_index = point_indices[key]
                        ids = source_ids[point_index]
                        if str(source_id) not in ids:
                            ids.append(str(source_id))
                    continue
                seen_points.add(key)
                point_indices[key] = len(points)
                points.append([x, height, z])
                source_ids.append([str(spawn["id"])] if spawn.get("id") is not None else [])
                marker_count += 1
                teleport_count += height is not None
        if realm == "pywel":
            type_id = type_index["trading_post"]
            points = points_by_type.setdefault(type_id, [])
            source_ids = source_ids_by_type.setdefault(type_id, [])
            for x, z in MAPGENIE_TRADING_CENTERS:
                nearest = min(
                    source_trading_points,
                    key=lambda item: (item[0] - x) ** 2 + (item[2] - z) ** 2,
                    default=None,
                )
                height = None
                if nearest and (nearest[0] - x) ** 2 + (nearest[2] - z) ** 2 <= 35 ** 2:
                    height = nearest[1]
                points.append([x, height, z])
                source_ids.append([])
                marker_count += 1
                teleport_count += height is not None
        realm_groups = []
        for type_id, points in sorted(points_by_type.items()):
            if not points:
                continue
            group_payload: dict[str, object] = {"type": type_id, "points": points}
            source_ids = source_ids_by_type.get(type_id, [[] for _ in points])
            if any(source_ids):
                group_payload["sourceIds"] = source_ids
            realm_groups.append(group_payload)
        realms[realm] = realm_groups

    # TH.GL publishes Abyss Gate records in the open-world payload even when
    # the object belongs to the elevated Abyss world layer. Keep the low-Y
    # surface entrances in Pywel and move only the high-Y internal gates.
    gate_type_id = type_index["abyss_gate"]
    pywel_gate_group = next(
        (group for group in realms.get("pywel", []) if group["type"] == gate_type_id),
        None,
    )
    if pywel_gate_group:
        pywel_points = pywel_gate_group["points"]
        pywel_source_ids = pywel_gate_group.get("sourceIds", [[] for _ in pywel_points])
        surface_points: list[list[float | None]] = []
        surface_source_ids: list[list[str]] = []
        abyss_points: list[list[float | None]] = []
        abyss_source_ids: list[list[str]] = []
        for point, source_ids in zip(pywel_points, pywel_source_ids, strict=True):
            target_points, target_source_ids = (
                (abyss_points, abyss_source_ids)
                if point[1] is not None and point[1] >= ABYSS_MIN_HEIGHT
                else (surface_points, surface_source_ids)
            )
            target_points.append(point)
            target_source_ids.append(source_ids)
        pywel_gate_group["points"] = surface_points
        pywel_gate_group["sourceIds"] = surface_source_ids
        if abyss_points:
            abyss_groups = realms.setdefault("abyss", [])
            abyss_gate_group = next(
                (group for group in abyss_groups if group["type"] == gate_type_id),
                None,
            )
            if abyss_gate_group is None:
                abyss_gate_group = {"type": gate_type_id, "points": [], "sourceIds": []}
                abyss_groups.append(abyss_gate_group)
                abyss_groups.sort(key=lambda group: group["type"])
            abyss_gate_group["points"].extend(abyss_points)
            abyss_gate_group.setdefault("sourceIds", []).extend(abyss_source_ids)

    catalog = {
        "version": 1,
        "source": {
            "name": "TH.GL + MapGenie",
            "url": "https://crimsondesert.th.gl/maps/Continent%20of%20Pywel",
            "licenseNote": "Public TH.GL node data with the Pywel Trading Center category refreshed from public MapGenie map data.",
        },
        "markerCount": marker_count,
        "teleportableCount": teleport_count,
        "groups": GROUPS,
        "types": types,
        "realms": realms,
    }
    target = PUBLIC / "data" / "marker-catalog.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    ICON_OUTPUT.mkdir(parents=True, exist_ok=True)
    for icon in sorted(used_icons):
        source = ICON_SOURCE / icon
        if source.exists():
            shutil.copy2(source, ICON_OUTPUT / icon)
        else:
            print(f"WARNING missing icon: {icon}")
    print(f"Built {marker_count} markers, {teleport_count} teleportable, {len(types)} types, {len(used_icons)} icons")


if __name__ == "__main__":
    main()
