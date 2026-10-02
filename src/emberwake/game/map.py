"""The map screen's view: which rooms of an area to draw, and where its icons go."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.world.spawning import WorldState, prefab_name
from emberwake.game.areas import area_of
from emberwake.game.flags import admits

if TYPE_CHECKING:
    from emberwake.engine.ecs.prefabs import Prefab
    from emberwake.engine.world.ldtk import EntityInstance, Level

MAP_PREFIX = "map."
"""An area's map is the inventory item ``map.<area>``."""


class Icon(StrEnum):
    BEACON_LIT = "beacon_lit"
    BEACON_COLD = "beacon_cold"
    NPC = "npc"
    CINDER = "cinder"
    PLAYER = "player"


@dataclass(frozen=True, slots=True)
class MapRoom:
    rect: pygame.Rect
    """Screen px, already shrunk by a pixel on each side."""
    visited: bool


@dataclass(frozen=True, slots=True)
class MapIcon:
    kind: Icon
    x: int
    y: int


@dataclass(slots=True)
class MapView:
    rooms: list[MapRoom] = field(default_factory=list)
    icons: list[MapIcon] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Known:
    """What the save knows: rooms entered, owned maps, flags and beacon states."""

    discovered: Collection[str]
    """Room iids."""
    inventory: Mapping[str, int]
    facts: Mapping[str, int]
    world: WorldState
    cinder: tuple[str, float, float] | None = None
    """Room and world px of the dropped embers."""


def map_view(
    levels: Mapping[str, Level],
    area: str,
    known: Known,
    *,
    prefabs: Mapping[str, Prefab],
    player: tuple[float, float],
    box: pygame.Rect,
) -> MapView:
    """The rooms of `area` to draw in `box` (screen px), and the icons on them."""
    rooms = {name: level for name, level in levels.items() if area_of(level) == area}
    if not rooms:
        return MapView()
    rects = {
        name: pygame.Rect(level.world_x, level.world_y, level.width, level.height)
        for name, level in rooms.items()
    }
    bounds = pygame.Rect.unionall(next(iter(rects.values())), list(rects.values()))
    scale = min(box.width / bounds.width, box.height / bounds.height)
    left = box.centerx - bounds.width * scale / 2
    top = box.centery - bounds.height * scale / 2

    def to(x: float, y: float) -> tuple[int, int]:
        return round(left + (x - bounds.x) * scale), round(top + (y - bounds.y) * scale)

    owned = known.inventory.get(MAP_PREFIX + area, 0) > 0
    view = MapView()
    shown: set[str] = set()
    for name, level in rooms.items():
        visited = level.iid in known.discovered
        if not (visited or owned):
            continue
        shown.add(name)
        rect = rects[name]
        (x0, y0), (x1, y1) = to(rect.left, rect.top), to(rect.right, rect.bottom)
        view.rooms.append(MapRoom(pygame.Rect(x0, y0, x1 - x0, y1 - y0).inflate(-2, -2), visited))
    for name in shown:
        level = rooms[name]
        for entity in level.entities():
            kind = _icon(entity, known, prefabs)
            if kind is not None:
                view.icons.append(MapIcon(kind, *to(*_centre(level, entity))))
    if known.cinder is not None and known.cinder[0] in shown:
        view.icons.append(MapIcon(Icon.CINDER, *to(*known.cinder[1:])))
    view.icons.append(MapIcon(Icon.PLAYER, *to(*player)))
    return view


def _icon(entity: EntityInstance, known: Known, prefabs: Mapping[str, Prefab]) -> Icon | None:
    if entity.identifier == "Beacon":
        saved = known.world.entities.get(entity.iid, {}).get("Beacon", {})
        return Icon.BEACON_LIT if saved.get("lit") else Icon.BEACON_COLD
    prefab = prefabs.get(prefab_name(entity.identifier))
    if prefab is not None and "Npc" in prefab.components and admits(entity, known.facts):
        return Icon.NPC
    return None


def _centre(level: Level, entity: EntityInstance) -> tuple[float, float]:
    x = level.world_x + entity.px[0] - entity.pivot[0] * entity.width + entity.width / 2
    y = level.world_y + entity.px[1] - entity.pivot[1] * entity.height + entity.height / 2
    return x, y
