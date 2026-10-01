"""Typed reader for LDtk projects (https://ldtk.io/json).

Only the parts the game needs are modelled; serde ignores everything else, so newer LDtk
versions keep loading. Projects saved with "external levels" are supported: level bodies are
read from their ``.ldtkl`` files on load.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from emberwake.engine.core.serde import alias, from_data
from emberwake.engine.physics.tiles import Tile, TileGrid

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

type LayerType = Literal["IntGrid", "Entities", "Tiles", "AutoLayer"]


@dataclass(slots=True)
class FieldInstance:
    """A custom field value on an entity or level."""

    identifier: str = alias("__identifier")
    type: str = alias("__type")
    value: Any = alias("__value", default=None)


def _plain(value: Any) -> Any:
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict) and "entityIid" in value:
        return value["entityIid"]
    return value


def _field(fields: list[FieldInstance], identifier: str, default: Any) -> Any:
    for instance in fields:
        if instance.identifier == identifier:
            return instance.value
    return default


@dataclass(slots=True)
class EntityInstance:
    """An entity placed in a level. ``px`` is relative to the level, at the entity's pivot."""

    identifier: str = alias("__identifier")
    iid: str = alias("iid")
    px: tuple[int, int] = alias("px")
    width: int = alias("width")
    height: int = alias("height")
    pivot: tuple[float, float] = alias("__pivot", default=(0.0, 0.0))
    tags: list[str] = alias("__tags", default_factory=list)
    field_instances: list[FieldInstance] = alias("fieldInstances", default_factory=list)

    def field(self, identifier: str, default: Any = None) -> Any:
        """Value of the custom field `identifier`, or `default` if the entity has none."""
        return _field(self.field_instances, identifier, default)

    def values(self) -> dict[str, Any]:
        """All custom fields, with entity refs replaced by the iid of the entity they point at."""
        return {f.identifier: _plain(f.value) for f in self.field_instances}


@dataclass(slots=True)
class TileInstance:
    """A tile drawn by a Tiles or AutoLayer layer."""

    px: tuple[int, int]
    src: tuple[int, int]
    f: int = 0
    """Flip bits: 1 = x, 2 = y."""
    t: int = 0
    a: float = 1.0


@dataclass(slots=True)
class LayerInstance:
    """One layer of one level."""

    identifier: str = alias("__identifier")
    type: LayerType = alias("__type")
    grid_size: int = alias("__gridSize")
    columns: int = alias("__cWid")
    rows: int = alias("__cHei")
    visible: bool = alias("visible", default=True)
    int_grid_csv: list[int] = alias("intGridCsv", default_factory=list)
    auto_layer_tiles: list[TileInstance] = alias("autoLayerTiles", default_factory=list)
    grid_tiles: list[TileInstance] = alias("gridTiles", default_factory=list)
    entity_instances: list[EntityInstance] = alias("entityInstances", default_factory=list)
    tileset_rel_path: str | None = alias("__tilesetRelPath", default=None)

    def to_tile_grid(self, legend: Mapping[int, Tile]) -> TileGrid:
        """Convert an IntGrid layer; values missing from `legend` become empty tiles."""
        if self.type != "IntGrid":
            msg = f"layer {self.identifier!r} is {self.type}, not IntGrid"
            raise ValueError(msg)
        cells = bytearray(legend.get(value, Tile.EMPTY) for value in self.int_grid_csv)
        return TileGrid(self.columns, self.rows, self.grid_size, cells)


@dataclass(slots=True)
class Neighbour:
    """A level touching this one in the world layout."""

    dir: str
    level_iid: str = alias("levelIid")


@dataclass(slots=True)
class Level:
    """One level (a room). ``layer_instances`` lists layers top-most first."""

    identifier: str = alias("identifier")
    iid: str = alias("iid")
    world_x: int = alias("worldX")
    world_y: int = alias("worldY")
    width: int = alias("pxWid")
    height: int = alias("pxHei")
    bg_color: str = alias("__bgColor", default="#000000")
    field_instances: list[FieldInstance] = alias("fieldInstances", default_factory=list)
    neighbours: list[Neighbour] = alias("__neighbours", default_factory=list)
    layer_instances: list[LayerInstance] | None = alias("layerInstances", default=None)
    external_rel_path: str | None = alias("externalRelPath", default=None)

    @property
    def layers(self) -> list[LayerInstance]:
        """Layers, top-most first. Empty until an external level body is loaded."""
        return self.layer_instances or []

    def layer(self, identifier: str) -> LayerInstance:
        """The layer called `identifier`."""
        for layer in self.layers:
            if layer.identifier == identifier:
                return layer
        msg = f"level {self.identifier!r} has no layer {identifier!r}"
        raise KeyError(msg)

    def entities(self, identifier: str | None = None) -> list[EntityInstance]:
        """Entities from every Entities layer, optionally only those called `identifier`."""
        return [
            entity
            for layer in self.layers
            if layer.type == "Entities"
            for entity in layer.entity_instances
            if identifier is None or entity.identifier == identifier
        ]

    def field(self, identifier: str, default: Any = None) -> Any:
        """Value of the level's custom field `identifier`."""
        return _field(self.field_instances, identifier, default)


@dataclass(slots=True)
class World:
    """A world of levels (projects with the multi-worlds option)."""

    identifier: str
    iid: str
    levels: list[Level] = field(default_factory=list)
    world_layout: str | None = alias("worldLayout", default=None)


@dataclass(slots=True)
class Project:
    """An LDtk project file."""

    json_version: str = alias("jsonVersion")
    levels: list[Level] = field(default_factory=list)
    worlds: list[World] = field(default_factory=list)
    external_levels: bool = alias("externalLevels", default=False)
    world_layout: str | None = alias("worldLayout", default=None)

    @property
    def all_levels(self) -> list[Level]:
        """Levels from the root and from every world."""
        return self.levels + [level for world in self.worlds for level in world.levels]

    def level(self, identifier: str) -> Level:
        """The level called `identifier`."""
        for level in self.all_levels:
            if level.identifier == identifier:
                return level
        msg = f"no level {identifier!r}"
        raise KeyError(msg)


def load_project(path: Path) -> Project:
    """Read an LDtk project, including the bodies of external levels."""
    project = from_data(Project, json.loads(path.read_text(encoding="utf-8")))
    for level in project.all_levels:
        if level.layer_instances is None and level.external_rel_path:
            body = from_data(Level, json.loads((path.parent / level.external_rel_path).read_text()))
            level.layer_instances = body.layers
    return project
