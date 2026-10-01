"""Compile a `Source` into LDtk project JSON, optionally merging into an existing project.

Generated levels carry the level field ``Generated = true``. A merge replaces those and keeps
every other level, so rooms made by hand in LDtk survive. ``defs.toml`` is the source of truth
for the entity types and level fields it lists; definitions it does not list are kept. Uids of
existing definitions and levels are kept, so hand-made levels keep pointing at the right defs.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from tools.levels.source import GRID, TILES, WORLD_CELL, SourceError

if TYPE_CHECKING:
    from tools.levels.source import Defs, EntitySpec, FieldSpec, Placed, Room, Source

LDTK_VERSION = "1.5.3"
NAMESPACE = uuid.UUID("6f1d6a1e-3c2b-4e8a-9a51-0c7e2a7d5b10")
GENERATED = "Generated"
LAYERS = (("Entities", "Entities"), ("Collisions", "IntGrid"))
INT_GRID_VALUES = (
    (TILES["#"], "Solid", "#3E3546"),
    (TILES["="], "OneWay", "#966C6C"),
    (TILES["^"], "Hazard", "#E83B3B"),
)
BG_COLOR = "#2E222F"

type Json = dict[str, Any]


def iid(name: str) -> str:
    """Stable iid, so rebuilding does not reshuffle identities that saves refer to."""
    return str(uuid.uuid5(NAMESPACE, name))


def is_generated(level: Json) -> bool:
    return any(
        field["__identifier"] == GENERATED and field["__value"] is True
        for field in level.get("fieldInstances", [])
    )


def build_project(source: Source, previous: Json | None = None) -> Json:
    """The project for `source`; with `previous`, its hand-made levels and defs are kept."""
    project = previous.copy() if previous else _skeleton()
    kept = [level for level in project.get("levels", []) if not is_generated(level)]
    clash = {level["identifier"] for level in kept} & {room.name for room in source.rooms}
    if clash:
        raise SourceError(f"hand-made levels {sorted(clash)} have the names of generated rooms")
    uids = Uids(previous)
    compiler = _Compiler(source, uids, project["dummyWorldIid"])
    project["defs"] = compiler.defs(project.get("defs"))
    project["levels"] = [compiler.level(room) for room in source.rooms] + kept
    link_neighbours(project["levels"])
    project["nextUid"] = uids.next
    return project


class Uids:
    """Hands out uids, reusing the ones `previous` gave the same definitions and levels."""

    def __init__(self, previous: Json | None) -> None:
        self.known: dict[str, int] = {}
        if previous is not None:
            defs = previous["defs"]
            for layer in defs["layers"]:
                self.known[f"layer:{layer['identifier']}"] = layer["uid"]
            for entity in defs["entities"]:
                self.known[f"entity:{entity['identifier']}"] = entity["uid"]
                for f in entity["fieldDefs"]:
                    self.known[f"field:{entity['identifier']}.{f['identifier']}"] = f["uid"]
            for f in defs["levelFields"]:
                self.known[f"level_field:{f['identifier']}"] = f["uid"]
            for level in previous["levels"]:
                self.known[f"level:{level['identifier']}"] = level["uid"]
        self.next = max(self.known.values(), default=0) + 1

    def __call__(self, key: str) -> int:
        if key not in self.known:
            self.known[key] = self.next
            self.next += 1
        return self.known[key]


class _Compiler:
    def __init__(self, source: Source, uids: Uids, world_iid: str) -> None:
        self.source = source
        self.uids = uids
        self.world_iid = world_iid
        self.refs = {
            (room.name, p.marker): self._entity_iid(room, p)
            for room in source.rooms
            for p in room.entities
            if p.count == 1
        }

    # Definitions

    def defs(self, previous: Json | None) -> Json:
        defs: Defs = self.source.defs
        old = previous or {"layers": [], "entities": [], "levelFields": []}
        ours = {name for name, _ in LAYERS}
        layers = [_layer_def(name, kind, self.uids(f"layer:{name}")) for name, kind in LAYERS]
        entities = [self._entity_def(name, spec) for name, spec in defs.entities.items()]
        level_fields = [
            _field_def(name, spec, self.uids(f"level_field:{name}"))
            for name, spec in defs.level_fields.items()
        ]
        return {
            **old,
            "layers": layers + [d for d in old["layers"] if d["identifier"] not in ours],
            "entities": entities
            + [d for d in old["entities"] if d["identifier"] not in defs.entities],
            "levelFields": level_fields
            + [d for d in old["levelFields"] if d["identifier"] not in defs.level_fields],
            "tilesets": old.get("tilesets", []),
            "enums": old.get("enums", []),
            "externalEnums": old.get("externalEnums", []),
        }

    def _entity_def(self, name: str, spec: EntitySpec) -> Json:
        fields = [
            _field_def(field, f, self.uids(f"field:{name}.{field}"))
            for field, f in self.source.defs.fields_of(spec).items()
        ]
        return _entity_def(name, spec, self.uids(f"entity:{name}"), fields)

    # Levels

    def level(self, room: Room) -> Json:
        defs = self.source.defs
        if GENERATED not in defs.level_fields:
            raise SourceError(f"defs.toml must define the level field {GENERATED}")
        unknown = room.fields.keys() - defs.level_fields.keys()
        if unknown:
            raise SourceError(f"{room.name}: unknown level fields {sorted(unknown)}")
        uid = self.uids(f"level:{room.name}")
        values = {**room.fields, GENERATED: True}
        fields = [
            self._field_instance(
                room,
                room.name,
                name,
                spec,
                values.get(name, spec.default),
                uid_key=f"level_field:{name}",
            )
            for name, spec in defs.level_fields.items()
        ]
        (width, height), (world_x, world_y) = room.size, room.world_px
        csv = [TILES.get(char, 0) for row in room.rows for char in row]
        entities = [self._entity(room, p) for p in room.entities]
        entities_uid, collisions_uid = self.uids("layer:Entities"), self.uids("layer:Collisions")
        return {
            "identifier": room.name,
            "iid": iid(f"level:{room.name}"),
            "uid": uid,
            "worldX": world_x,
            "worldY": world_y,
            "worldDepth": 0,
            "pxWid": width * GRID,
            "pxHei": height * GRID,
            "__bgColor": BG_COLOR,
            "bgColor": None,
            "useAutoIdentifier": False,
            "bgRelPath": None,
            "bgPos": None,
            "bgPivotX": 0.5,
            "bgPivotY": 0.5,
            "__smartColor": "#ADADB5",
            "__bgPos": None,
            "externalRelPath": None,
            "fieldInstances": fields,
            "layerInstances": [
                _layer_instance(room, "Entities", entities_uid, uid, entities=entities),
                _layer_instance(room, "Collisions", collisions_uid, uid, csv=csv),
            ],
            "__neighbours": [],
        }

    def _entity_iid(self, room: Room, p: Placed) -> str:
        suffix = "" if p.count == 1 else f":{p.index}"
        return iid(f"entity:{room.name}:{p.marker}{suffix}")

    def _entity(self, room: Room, p: Placed) -> Json:
        spec = self.source.defs.entities.get(p.type)
        where = f"{room.name} ({p.column}, {p.row})"
        if spec is None:
            raise SourceError(f"{where}: unknown entity type {p.type!r}")
        width, height = p.columns * GRID, p.rows * GRID
        if not spec.resizable and (width, height) != spec.size:
            raise SourceError(f"{where}: {p.type} must be {spec.size} px, not {(width, height)}")
        fields = self.source.defs.fields_of(spec)
        unknown = p.fields.keys() - fields.keys()
        if unknown:
            raise SourceError(f"{where}: {p.type} has no fields {sorted(unknown)}")
        if spec.max_count and sum(e.type == p.type for e in room.entities) > spec.max_count:
            raise SourceError(f"{room.name}: more than {spec.max_count} {p.type}")
        px = [
            round(p.column * GRID + spec.pivot[0] * width),
            round(p.row * GRID + spec.pivot[1] * height),
        ]
        world_x, world_y = room.world_px
        return {
            "__identifier": p.type,
            "__grid": [px[0] // GRID, px[1] // GRID],
            "__pivot": list(spec.pivot),
            "__tags": [],
            "__tile": None,
            "__smartColor": spec.color.upper(),
            "__worldX": world_x + px[0],
            "__worldY": world_y + px[1],
            "iid": self._entity_iid(room, p),
            "width": width,
            "height": height,
            "defUid": self.uids(f"entity:{p.type}"),
            "px": px,
            "fieldInstances": [
                self._field_instance(
                    room,
                    where,
                    name,
                    f,
                    p.fields.get(name, f.default),
                    uid_key=f"field:{p.type}.{name}",
                )
                for name, f in fields.items()
            ],
        }

    def _field_instance(
        self, room: Room, where: str, name: str, spec: FieldSpec, value: Any, *, uid_key: str
    ) -> Json:
        if spec.array:
            items = [] if value is None else value
            if not isinstance(items, list):
                raise SourceError(f"{where}: {name} must be a list")
        else:
            items = [] if value is None else [value]
        converted = [self._value(f"{where} {name}", spec, item, room) for item in items]
        type_name = f"Array<{spec.type}>" if spec.array else spec.type
        return {
            "__identifier": name,
            "__type": type_name,
            "__value": converted if spec.array else (converted[0] if converted else None),
            "__tile": None,
            "defUid": self.uids(uid_key),
            "realEditorValues": [_editor_value(spec, item) for item in converted],
        }

    def _value(self, where: str, spec: FieldSpec, value: Any, room: Room) -> Any:
        if spec.type == "EntityRef":
            if not isinstance(value, str):
                raise SourceError(f"{where}: entity refs are marker strings like 'a' or 'Room:a'")
            return self._ref(where, room, value)
        number = isinstance(value, int | float) and not isinstance(value, bool)
        valid = {
            "Bool": isinstance(value, bool),
            "Int": number and isinstance(value, int),
            "Float": number,
            "String": isinstance(value, str),
        }
        if not valid[spec.type]:
            raise SourceError(f"{where}: expected {spec.type}, got {value!r}")
        return float(value) if spec.type == "Float" else value

    def _ref(self, where: str, room: Room, ref: str) -> Json:
        room_name, _, marker = ref.rpartition(":")
        target = room_name or room.name
        entity_iid = self.refs.get((target, marker))
        if entity_iid is None:
            raise SourceError(f"{where}: {ref!r} is not a single entity marker in {target}")
        return {
            "entityIid": entity_iid,
            "layerIid": iid(f"layer:{target}:Entities"),
            "levelIid": iid(f"level:{target}"),
            "worldIid": self.world_iid,
        }


def link_neighbours(levels: list[Json]) -> None:
    """Recompute ``__neighbours`` for levels sharing an edge."""
    for level in levels:
        level["__neighbours"] = []
    for i, a in enumerate(levels):
        for b in levels[i + 1 :]:
            sides = _touching(a, b)
            if sides:
                a["__neighbours"].append({"dir": sides[0], "levelIid": b["iid"]})
                b["__neighbours"].append({"dir": sides[1], "levelIid": a["iid"]})


def _touching(a: Json, b: Json) -> tuple[str, str] | None:
    """Which side of `a` touches `b`, and which side of `b` touches `a`."""
    ax, ay, aw, ah = a["worldX"], a["worldY"], a["pxWid"], a["pxHei"]
    bx, by, bw, bh = b["worldX"], b["worldY"], b["pxWid"], b["pxHei"]
    rows_overlap = ay < by + bh and by < ay + ah
    columns_overlap = ax < bx + bw and bx < ax + aw
    if rows_overlap and bx == ax + aw:
        return "e", "w"
    if rows_overlap and ax == bx + bw:
        return "w", "e"
    if columns_overlap and by == ay + ah:
        return "s", "n"
    if columns_overlap and ay == by + bh:
        return "n", "s"
    return None


def _editor_value(spec: FieldSpec, value: Any) -> Json:
    if spec.type == "EntityRef":
        return {"id": "V_String", "params": [value["entityIid"]]}
    return {"id": f"V_{spec.type}", "params": [value]}


def _skeleton() -> Json:
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
        "nextUid": 1,
        "identifierStyle": "Capitalize",
        "toc": [],
        "worldLayout": "GridVania",
        "worldGridWidth": WORLD_CELL[0] * GRID,
        "worldGridHeight": WORLD_CELL[1] * GRID,
        "defaultLevelWidth": WORLD_CELL[0] * GRID * 4,
        "defaultLevelHeight": WORLD_CELL[1] * GRID * 3,
        "defaultPivotX": 0.0,
        "defaultPivotY": 0.0,
        "defaultGridSize": GRID,
        "defaultEntityWidth": GRID,
        "defaultEntityHeight": GRID,
        "bgColor": "#40465B",
        "defaultLevelBgColor": BG_COLOR,
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
        "defs": None,
        "levels": [],
        "worlds": [],
        "dummyWorldIid": iid("world"),
    }


def _layer_def(identifier: str, kind: str, uid: int) -> Json:
    values = [
        {"value": value, "identifier": name, "color": color, "tile": None, "groupUid": 0}
        for value, name, color in INT_GRID_VALUES
    ]
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
        "intGridValues": values if kind == "IntGrid" else [],
        "intGridValuesGroups": [],
        "autoRuleGroups": [],
        "autoSourceLayerDefUid": None,
        "tilesetDefUid": None,
        "tilePivotX": 0.0,
        "tilePivotY": 0.0,
        "biomeFieldUid": None,
    }


def _entity_def(identifier: str, spec: EntitySpec, uid: int, fields: list[Json]) -> Json:
    return {
        "identifier": identifier,
        "uid": uid,
        "tags": [],
        "exportToToc": False,
        "allowOutOfBounds": False,
        "doc": spec.doc,
        "width": spec.size[0],
        "height": spec.size[1],
        "resizableX": spec.resizable,
        "resizableY": spec.resizable,
        "minWidth": None,
        "maxWidth": None,
        "minHeight": None,
        "maxHeight": None,
        "keepAspectRatio": False,
        "tileOpacity": 1.0,
        "fillOpacity": 0.08,
        "lineOpacity": 1.0,
        "hollow": False,
        "color": spec.color.upper(),
        "renderMode": "Rectangle" if spec.resizable else "Cross",
        "showName": True,
        "tilesetId": None,
        "tileRenderMode": "FitInside",
        "tileRect": None,
        "uiTileRect": None,
        "nineSliceBorders": [],
        "maxCount": spec.max_count,
        "limitScope": "PerLevel",
        "limitBehavior": "MoveLastOne",
        "pivotX": spec.pivot[0],
        "pivotY": spec.pivot[1],
        "fieldDefs": fields,
    }


def _field_def(identifier: str, spec: FieldSpec, uid: int) -> Json:
    ref = spec.type == "EntityRef"
    default = None
    if spec.default is not None and not spec.array:
        default = {"id": f"V_{spec.type}", "params": [spec.default]}
    return {
        "identifier": identifier,
        "doc": spec.doc,
        "__type": f"Array<{spec.type}>" if spec.array else spec.type,
        "uid": uid,
        "type": f"F_{spec.type}",
        "isArray": spec.array,
        "canBeNull": spec.default is None and not spec.array,
        "arrayMinLength": None,
        "arrayMaxLength": None,
        "editorDisplayMode": "RefLinkBetweenCenters" if ref else "NameAndValue",
        "editorDisplayScale": 1.0,
        "editorDisplayPos": "Above",
        "editorLinkStyle": "CurvedArrow",
        "editorDisplayColor": None,
        "editorAlwaysShow": False,
        "editorShowInWorld": True,
        "editorCutLongValues": True,
        "editorTextSuffix": None,
        "editorTextPrefix": None,
        "useForSmartColor": False,
        "exportToToc": False,
        "searchable": False,
        "min": None,
        "max": None,
        "regex": None,
        "acceptFileTypes": None,
        "defaultOverride": default,
        "textLanguageMode": None,
        "symmetricalRef": False,
        "autoChainRef": True,
        "allowOutOfLevelRef": True,
        "allowedRefs": "Any",
        "allowedRefsEntityUid": None,
        "allowedRefTags": [],
        "tilesetUid": None,
    }


def _layer_instance(
    room: Room,
    identifier: str,
    def_uid: int,
    level_uid: int,
    *,
    csv: list[int] | None = None,
    entities: list[Json] | None = None,
) -> Json:
    columns, rows = room.size
    return {
        "__identifier": identifier,
        "__type": "IntGrid" if csv is not None else "Entities",
        "__cWid": columns,
        "__cHei": rows,
        "__gridSize": GRID,
        "__opacity": 1.0,
        "__pxTotalOffsetX": 0,
        "__pxTotalOffsetY": 0,
        "__tilesetDefUid": None,
        "__tilesetRelPath": None,
        "iid": iid(f"layer:{room.name}:{identifier}"),
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
