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
    for _ in range(3):
        for key, value in list(result.items()):
            if value.startswith("@") and value in result:
                result[key] = result[value]
    return result


def group_for(marker_type: str) -> str:
    value = marker_type.lower()
    if value.startswith("abyss_") or value in {"sealed_artifact", "faction_node"}:
        return "abyss"
    if "quest" in value or "bounty" in value:
        return "quests"
    if any(word in value for word in ("chest", "treasure", "artifact", "collect", "memory_fragment", "legendary", "key_item")):
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
    source_groups = {
        "pywel": json.loads((WORK / "thgl-openworld.json").read_text(encoding="utf-8")),
        "abyss": json.loads((WORK / "thgl-abyss.json").read_text(encoding="utf-8")),
    }
    marker_types = sorted({group["type"] for groups in source_groups.values() for group in groups})
    type_index = {marker_type: index for index, marker_type in enumerate(marker_types)}
    types = []
    used_icons = {group["icon"] for group in GROUPS}
    for marker_type in marker_types:
        group_id = group_for(marker_type)
        icon = icon_for(marker_type, group_id)
        used_icons.add(icon)
        fallback = marker_type.replace("_", " ").title()
        types.append({
            "id": marker_type,
            "name": ru.get(marker_type) or en.get(marker_type) or fallback,
            "nameEn": en.get(marker_type) or fallback,
            "description": description_for(marker_type, ru.get(marker_type) or en.get(marker_type) or fallback, group_id),
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
        seen_points: set[tuple[int, float, float | None, float]] = set()
        for group in groups:
            type_id = type_index[group["type"]]
            points = points_by_type.setdefault(type_id, [])
            for spawn in group.get("spawns", []):
                p = spawn.get("p", [])
                if len(p) < 2:
                    continue
                # TH.GL/Leaflet stores [game Z, game X, game Y].
                height = round(float(p[2]), 3) if len(p) > 2 and float(p[2]) != 0 else None
                x = round(float(p[1]), 3)
                z = round(float(p[0]), 3)
                key = (type_id, x, height, z)
                if key in seen_points:
                    continue
                seen_points.add(key)
                points.append([x, height, z])
                marker_count += 1
                teleport_count += height is not None
        realm_groups = [
            {"type": type_id, "points": points}
            for type_id, points in sorted(points_by_type.items())
            if points
        ]
        realms[realm] = realm_groups

    catalog = {
        "version": 1,
        "source": {
            "name": "TH.GL",
            "url": "https://crimsondesert.th.gl/maps/Continent%20of%20Pywel",
            "licenseNote": "Public map node data; names localized from the public Russian map page.",
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
