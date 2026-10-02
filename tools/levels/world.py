"""The world as the checks see it: every room's tiles in world cells, every entity and the rules."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tools.levels.reach import Cell

from emberwake.engine.core.dialogue import Graph, load_dialogues
from emberwake.engine.ecs.prefabs import Prefab
from emberwake.engine.physics import Tile
from emberwake.engine.world.ldtk import EntityInstance, Level, Project
from emberwake.engine.world.spawning import prefab_name
from emberwake.game.grants import START, GrantSpec, load_grants
from emberwake.game.lamprey import FLAGS as LAMPREY_FLAGS
from emberwake.game.scenes.gameplay import COLLISIONS, DEFAULT_ROOM
from emberwake.game.shop import load_shops
from emberwake.game.signals import TARGETS
from emberwake.game.trials import load_trials

if TYPE_CHECKING:
    from pathlib import Path

NEAR = 6
"""Tiles from an entrance to the nearest PlayerStart."""
LAB = "lab"
"""The area of the dev rooms: not part of the game's world."""
BODY = 2
"""Tiles tall the player is, so the narrowest doorway between side-by-side rooms."""


@dataclass(slots=True)
class Rules:
    """What the checks read besides the levels."""

    start: str = DEFAULT_ROOM
    abilities: tuple[str, ...] = START
    grants: Mapping[str, GrantSpec] = field(default_factory=dict)
    dialogues: Mapping[str, Graph] = field(default_factory=dict)
    shop_flags: Collection[str] = ()
    code_flags: Collection[str] = ()
    """Flags the game itself sets, such as a boss's defeat."""
    shop_grants: Collection[str] = ()
    trials: Collection[str] = ()
    """Rooms entered from the menu, outside the world."""


def load_rules(content: Path) -> Rules:
    """The rules of the game's content directory."""
    items = [
        item for shop in load_shops(content / "shop.toml").values() for item in shop.items.values()
    ]
    return Rules(
        grants=load_grants(content / "grants.toml"),
        dialogues=load_dialogues(content / "dialogue.toml"),
        shop_flags={item.flag for item in items if item.flag},
        code_flags=LAMPREY_FLAGS,
        shop_grants={item.grant for item in items if item.grant},
        trials={trial.room for trial in load_trials(content / "trials.toml").values()},
    )


@dataclass(slots=True, eq=False)
class Thing:
    """An entity placed in the world, with the cells it covers."""

    room: str
    entity: EntityInstance
    prefab: Prefab | None
    cells: frozenset[Cell]

    @property
    def kind(self) -> str:
        return self.entity.identifier

    @property
    def iid(self) -> str:
        return self.entity.iid

    def targets(self) -> Iterator[str]:
        """The entities this one signals."""
        if self.prefab is not None:
            values = self.entity.values()
            for name, target in self.prefab.fields.items():
                if target in TARGETS:
                    yield from values.get(name) or []


@dataclass(slots=True)
class Index:
    """Every room's tiles in world cells, and every entity."""

    levels: dict[str, Level] = field(default_factory=dict)
    tiles: dict[Cell, Tile] = field(default_factory=dict)
    owner: dict[Cell, str] = field(default_factory=dict)
    things: list[Thing] = field(default_factory=list)
    starts: dict[str, list[Cell]] = field(default_factory=lambda: defaultdict(list))

    def lab(self, room: str) -> bool:
        return self.levels[room].field("Area") == LAB


def index(project: Project, prefabs: Mapping[str, Prefab]) -> Index:
    """Read the project into world cells."""
    found = Index()
    for level in project.all_levels:
        found.levels[level.identifier] = level
        try:
            layer = level.layer("Collisions")
        except KeyError:
            continue
        size = layer.grid_size
        left, top = level.world_x // size, level.world_y // size
        grid = layer.to_tile_grid(COLLISIONS)
        for row in range(grid.height):
            for column in range(grid.width):
                found.tiles[left + column, top + row] = grid.get(column, row)
                found.owner[left + column, top + row] = level.identifier
        for entity in level.entities():
            x = level.world_x + entity.px[0] - entity.pivot[0] * entity.width
            y = level.world_y + entity.px[1] - entity.pivot[1] * entity.height
            cells = frozenset(
                (column, row)
                for column in range(math.floor(x / size), math.ceil((x + entity.width) / size))
                for row in range(math.floor(y / size), math.ceil((y + entity.height) / size))
            )
            found.things.append(
                Thing(level.identifier, entity, prefabs.get(prefab_name(entity.identifier)), cells)
            )
            if entity.identifier == "PlayerStart":
                column = (level.world_x + entity.px[0]) // size
                row = (level.world_y + entity.px[1] - 1) // size
                found.starts[level.identifier].append((column, row))
    return found
