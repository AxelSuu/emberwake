"""Bootstrap an LDtk project from ASCII room maps.

Each room file is a grid of characters, one per 16 px tile:

    #  solid        =  one-way platform     ^  hazard
    P  PlayerStart (empty tile, entity at its bottom centre)
    anything else is empty

Rooms are laid out left to right in a GridVania world. The output validates against the
official LDtk JSON schema and opens in the LDtk editor, which is the source of truth afterwards:
this tool refuses to overwrite an existing project unless given --force.

    uv run python tools/ldtk_scaffold.py levels/world.ldtk levels/ascii/*.txt
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LDTK_VERSION = "1.5.3"
GRID = 16
WORLD_GRID = (320, 176)
COLLISIONS_UID = 1
ENTITIES_UID = 2
PLAYER_START_UID = 3
FIRST_LEVEL_UID = 100

INT_GRID_VALUES = {
    "#": (1, "Solid", "#3E3546"),
    "=": (2, "OneWay", "#966C6C"),
    "^": (3, "Hazard", "#E83B3B"),
}
ENTITY_MARKERS = {"P": ("PlayerStart", PLAYER_START_UID, "#F9C22B")}
NAMESPACE = uuid.UUID("6f1d6a1e-3c2b-4e8a-9a51-0c7e2a7d5b10")

type Json = dict[str, Any]


def iid(name: str) -> str:
    """Stable iid, so regenerating a project does not reshuffle identities."""
    return str(uuid.uuid5(NAMESPACE, name))


def parse_room(text: str) -> list[str]:
    rows = [line.rstrip("\n") for line in text.splitlines() if line.strip()]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        msg = "room rows must be non-empty and of equal length"
        raise ValueError(msg)
    return rows


def build_project(rooms: Mapping[str, Sequence[str]]) -> Json:
    """Build an LDtk project dict from ``{identifier: rows}``."""
    levels = []
    world_x = 0
    for index, (name, rows) in enumerate(rooms.items()):
        levels.append(_level(name, rows, FIRST_LEVEL_UID + index, world_x))
        world_x += _snap(len(rows[0]) * GRID, WORLD_GRID[0])
    _link_neighbours(levels)
    return {
        "__header__": {
            "fileType": "LDtk Project JSON",
            "app": "LDtk",
            "doc": "https://ldtk.io/json",
            "schema": "https://ldtk.io/files/JSON_SCHEMA.json",
            "appAuthor": "Sebastien 'deepnight' Benard",
            "appVersion": LDTK_VERSION,
            "url": "https://ldtk.io",
        },
        "iid": iid("project"),
        "jsonVersion": LDTK_VERSION,
        "appBuildId": 473703.0,
        "nextUid": FIRST_LEVEL_UID + len(levels),
        "identifierStyle": "Capitalize",
        "toc": [],
        "worldLayout": "GridVania",
        "worldGridWidth": WORLD_GRID[0],
        "worldGridHeight": WORLD_GRID[1],
        "defaultLevelWidth": WORLD_GRID[0] * 4,
        "defaultLevelHeight": WORLD_GRID[1] * 3,
        "defaultPivotX": 0.0,
        "defaultPivotY": 0.0,
        "defaultGridSize": GRID,
        "defaultEntityWidth": GRID,
        "defaultEntityHeight": GRID,
        "bgColor": "#40465B",
        "defaultLevelBgColor": "#2E222F",
        "minifyJson": False,
        "externalLevels": False,
        "exportTiled": False,
        "simplifiedExport": False,
        "imageExportMode": "None",
        "exportLevelBg": True,
        "pngFilePattern": None,
        "backupOnSave": False,
        "backupLimit": 10,
        "backupRelPath": None,
        "levelNamePattern": "Level_%idx",
        "tutorialDesc": None,
        "customCommands": [],
        "flags": [],
        "defs": _definitions(),
        "levels": levels,
        "worlds": [],
        "dummyWorldIid": iid("world"),
    }


def _snap(value: int, step: int) -> int:
    return -(-value // step) * step


def _definitions() -> Json:
    return {
        "layers": [
            _layer_def("Entities", ENTITIES_UID, "Entities", []),
            _layer_def(
                "Collisions",
                COLLISIONS_UID,
                "IntGrid",
                [
                    {
                        "value": value,
                        "identifier": name,
                        "color": color,
                        "tile": None,
                        "groupUid": 0,
                    }
                    for value, name, color in INT_GRID_VALUES.values()
                ],
            ),
        ],
        "entities": [_entity_def(*marker) for marker in ENTITY_MARKERS.values()],
        "tilesets": [],
        "enums": [],
        "externalEnums": [],
        "levelFields": [],
    }


def _layer_def(identifier: str, uid: int, kind: str, values: list[Json]) -> Json:
    return {
        "__type": kind,
        "identifier": identifier,
        "type": kind,
        "uid": uid,
        "doc": None,
        "uiColor": None,
        "gridSize": GRID,
        "guideGridWid": 0,
        "guideGridHei": 0,
        "displayOpacity": 1.0,
        "inactiveOpacity": 1.0,
        "hideInList": False,
        "hideFieldsWhenInactive": True,
        "canSelectWhenInactive": True,
        "renderInWorldView": True,
        "pxOffsetX": 0,
        "pxOffsetY": 0,
        "parallaxFactorX": 0.0,
        "parallaxFactorY": 0.0,
        "parallaxScaling": True,
        "requiredTags": [],
        "excludedTags": [],
        "autoTilesKilledByOtherLayerUid": None,
        "uiFilterTags": [],
        "useAsyncRender": False,
        "intGridValues": values,
        "intGridValuesGroups": [],
        "autoRuleGroups": [],
        "autoSourceLayerDefUid": None,
        "tilesetDefUid": None,
        "tilePivotX": 0.0,
        "tilePivotY": 0.0,
        "biomeFieldUid": None,
    }


def _int_grid_value(value: int, identifier: str, color: str) -> Json:
    return {"value": value, "identifier": identifier, "color": color, "tile": None, "groupUid": 0}


def _entity_def(identifier: str, uid: int, color: str) -> Json:
    return {
        "identifier": identifier,
        "uid": uid,
        "tags": [],
        "exportToToc": False,
        "allowOutOfBounds": False,
        "doc": None,
        "width": GRID,
        "height": GRID,
        "resizableX": False,
        "resizableY": False,
        "minWidth": None,
        "maxWidth": None,
        "minHeight": None,
        "maxHeight": None,
        "keepAspectRatio": False,
        "tileOpacity": 1.0,
        "fillOpacity": 0.08,
        "lineOpacity": 1.0,
        "hollow": False,
        "color": color,
        "renderMode": "Cross",
        "showName": True,
        "tilesetId": None,
        "tileRenderMode": "FitInside",
        "tileRect": None,
        "uiTileRect": None,
        "nineSliceBorders": [],
        "maxCount": 1,
        "limitScope": "PerLevel",
        "limitBehavior": "MoveLastOne",
        "pivotX": 0.5,
        "pivotY": 1.0,
        "fieldDefs": [],
    }


def _level(name: str, rows: Sequence[str], uid: int, world_x: int) -> Json:
    columns, height = size = len(rows[0]), len(rows)
    csv = [
        INT_GRID_VALUES[char][0] if char in INT_GRID_VALUES else 0 for row in rows for char in row
    ]
    entities = [
        _entity(name, char, column, row, world_x)
        for row, line in enumerate(rows)
        for column, char in enumerate(line)
        if char in ENTITY_MARKERS
    ]
    return {
        "identifier": name,
        "iid": iid(f"level:{name}"),
        "uid": uid,
        "worldX": world_x,
        "worldY": 0,
        "worldDepth": 0,
        "pxWid": columns * GRID,
        "pxHei": height * GRID,
        "__bgColor": "#2E222F",
        "bgColor": None,
        "useAutoIdentifier": False,
        "bgRelPath": None,
        "bgPos": None,
        "bgPivotX": 0.5,
        "bgPivotY": 0.5,
        "__smartColor": "#ADADB5",
        "__bgPos": None,
        "externalRelPath": None,
        "fieldInstances": [],
        "layerInstances": [
            _layer_instance(name, "Entities", ENTITIES_UID, uid, size, entities=entities),
            _layer_instance(name, "Collisions", COLLISIONS_UID, uid, size, csv=csv),
        ],
        "__neighbours": [],
    }


def _layer_instance(
    level: str,
    identifier: str,
    def_uid: int,
    level_uid: int,
    size: tuple[int, int],
    *,
    csv: list[int] | None = None,
    entities: list[Json] | None = None,
) -> Json:
    return {
        "__identifier": identifier,
        "__type": "IntGrid" if csv is not None else "Entities",
        "__cWid": size[0],
        "__cHei": size[1],
        "__gridSize": GRID,
        "__opacity": 1.0,
        "__pxTotalOffsetX": 0,
        "__pxTotalOffsetY": 0,
        "__tilesetDefUid": None,
        "__tilesetRelPath": None,
        "iid": iid(f"layer:{level}:{identifier}"),
        "levelId": level_uid,
        "layerDefUid": def_uid,
        "pxOffsetX": 0,
        "pxOffsetY": 0,
        "visible": True,
        "optionalRules": [],
        "intGridCsv": csv or [],
        "autoLayerTiles": [],
        "seed": 1_000_000 + level_uid,
        "overrideTilesetUid": None,
        "gridTiles": [],
        "entityInstances": entities or [],
    }


def _entity(level: str, char: str, column: int, row: int, world_x: int) -> Json:
    identifier, def_uid, color = ENTITY_MARKERS[char]
    px = [column * GRID + GRID // 2, (row + 1) * GRID]
    return {
        "__identifier": identifier,
        "__grid": [px[0] // GRID, px[1] // GRID],
        "__pivot": [0.5, 1.0],
        "__tags": [],
        "__tile": None,
        "__smartColor": color,
        "__worldX": world_x + px[0],
        "__worldY": px[1],
        "iid": iid(f"entity:{level}:{identifier}:{column}:{row}"),
        "width": GRID,
        "height": GRID,
        "defUid": def_uid,
        "px": px,
        "fieldInstances": [],
    }


def _link_neighbours(levels: list[Json]) -> None:
    for left, right in itertools.pairwise(levels):
        left["__neighbours"].append({"dir": "e", "levelIid": right["iid"]})
        right["__neighbours"].append({"dir": "w", "levelIid": left["iid"]})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path)
    parser.add_argument("rooms", type=Path, nargs="+", help="ASCII room files; stem = identifier")
    parser.add_argument("--force", action="store_true", help="overwrite an existing project")
    args = parser.parse_args(argv)
    if args.output.exists() and not args.force:
        print(f"{args.output} exists; edit it in LDtk or pass --force", file=sys.stderr)
        return 1
    rooms = {
        path.stem.title().replace(" ", "_"): parse_room(path.read_text()) for path in args.rooms
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_project(rooms), indent="\t") + "\n")
    print(f"Wrote {args.output} with {len(rooms)} room(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
