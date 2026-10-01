"""Rooms of a GridVania world in world coordinates: layout, streaming and tile queries.

`RoomGraph` knows every room's rect and which rooms share an edge. `RoomStreamer` keeps the
active room and its neighbours loaded and unloads the rest. `WorldGrid` answers tile queries in
world cells by routing them to whichever loaded room owns the cell, so physics never sees room
boundaries.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics.tiles import Tile, TileGrid
from emberwake.engine.world.ldtk import Level

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class RoomEntered:
    """The player's centre moved into another room."""

    room: str
    previous: str | None
    x: float
    y: float
    """Where the player entered, in world pixels."""


class RoomGraph:
    """Room rects in world pixels and adjacency computed from them."""

    def __init__(self, levels: Iterable[Level]) -> None:
        self.levels: dict[str, Level] = {level.identifier: level for level in levels}
        self.rects = {
            name: pygame.Rect(level.world_x, level.world_y, level.width, level.height)
            for name, level in self.levels.items()
        }
        self._neighbours: dict[str, list[str]] = {name: [] for name in self.levels}
        names = list(self.levels)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                if _share_edge(self.rects[a], self.rects[b]):
                    self._neighbours[a].append(b)
                    self._neighbours[b].append(a)

    def neighbours(self, room: str) -> list[str]:
        """Rooms sharing an edge with `room`."""
        return self._neighbours[room]

    def room_at(self, x: float, y: float) -> str | None:
        """The room containing the point, if any."""
        for name, rect in self.rects.items():
            if rect.left <= x < rect.right and rect.top <= y < rect.bottom:
                return name
        return None

    def within(self, room: str, steps: int) -> set[str]:
        """Rooms at most `steps` edges away from `room`, including itself."""
        found = {room}
        queue = deque([(room, 0)])
        while queue:
            current, distance = queue.popleft()
            if distance == steps:
                continue
            for neighbour in self._neighbours[current]:
                if neighbour not in found:
                    found.add(neighbour)
                    queue.append((neighbour, distance + 1))
        return found


def _share_edge(a: pygame.Rect, b: pygame.Rect) -> bool:
    rows = a.top < b.bottom and b.top < a.bottom
    columns = a.left < b.right and b.left < a.right
    return (rows and (a.right == b.left or b.right == a.left)) or (
        columns and (a.bottom == b.top or b.bottom == a.top)
    )


@dataclass(slots=True)
class Room:
    """A loaded room: its level and collision grid, placed in world cells.

    Attributes:
        rect: Bounds in world pixels.
        cell: World cell of the top-left tile.
    """

    level: Level
    grid: TileGrid
    rect: pygame.Rect = field(init=False)
    cell: tuple[int, int] = field(init=False)

    def __post_init__(self) -> None:
        level, size = self.level, self.grid.tile_size
        self.rect = pygame.Rect(level.world_x, level.world_y, level.width, level.height)
        self.cell = level.world_x // size, level.world_y // size

    @property
    def name(self) -> str:
        """The level identifier."""
        return self.level.identifier


class WorldGrid:
    """A `TileSource` over the loaded rooms; cells outside them are empty."""

    def __init__(self, tile_size: int = 16) -> None:
        self._tile_size = tile_size
        self.rooms: list[Room] = []
        self._last: Room | None = None

    @property
    def tile_size(self) -> int:
        """Cell size in pixels."""
        return self._tile_size

    def add(self, room: Room) -> None:
        """Start routing queries to `room`.

        Raises:
            ValueError: The room is not aligned to the tile grid or uses another tile size.
        """
        level, size = room.level, self._tile_size
        if room.grid.tile_size != size or level.world_x % size or level.world_y % size:
            msg = f"room {room.name} is not aligned to the {size} px grid"
            raise ValueError(msg)
        self.rooms.append(room)

    def remove(self, room: Room) -> None:
        """Stop routing queries to `room`."""
        self.rooms.remove(room)
        if self._last is room:
            self._last = None

    def get(self, column: int, row: int) -> Tile:
        """Tile at a world cell."""
        room = self._last
        if room is None or not _owns(room, column, row):
            room = next((r for r in self.rooms if _owns(r, column, row)), None)
            if room is None:
                return Tile.EMPTY
            self._last = room
        left, top = room.cell
        return room.grid.get(column - left, row - top)

    def void(self, x: float, y: float) -> bool:
        """Whether (`x`, `y`) is below every loaded room spanning `x`, or no room spans it."""
        spans = [room.rect for room in self.rooms if room.rect.left <= x < room.rect.right]
        return all(y > rect.bottom for rect in spans)


def _owns(room: Room, column: int, row: int) -> bool:
    left, top = room.cell
    return 0 <= column - left < room.grid.width and 0 <= row - top < room.grid.height


type RoomHook = Callable[[Room], None]


class RoomStreamer:
    """Keeps the active room and its neighbours loaded in a `WorldGrid`.

    Args:
        graph: The world layout.
        grid: Receives loaded rooms.
        layer: IntGrid layer holding collisions.
        legend: IntGrid value to tile kind.
        on_load: Called after a room is added to `grid`.
        on_unload: Called before a room is removed from `grid`, so its entities can be saved.
    """

    def __init__(
        self,
        graph: RoomGraph,
        grid: WorldGrid,
        layer: str,
        legend: Mapping[int, Tile],
        *,
        on_load: RoomHook | None = None,
        on_unload: RoomHook | None = None,
    ) -> None:
        self.graph = graph
        self.grid = grid
        self.layer = layer
        self.legend = legend
        self.on_load = on_load
        self.on_unload = on_unload
        self.active: str | None = None
        self.loaded: dict[str, Room] = {}

    def enter(self, room: str) -> None:
        """Make `room` active: load it and its neighbours, unload rooms two or more steps away."""
        self.active = room
        keep = self.graph.within(room, 1)
        for name in [name for name in self.loaded if name not in keep]:
            self.unload(name)
        for name in [room, *self.graph.neighbours(room)]:
            if name not in self.loaded:
                self._load(name)

    def unload(self, name: str) -> None:
        """Remove a loaded room."""
        room = self.loaded.pop(name)
        if self.on_unload is not None:
            self.on_unload(room)
        self.grid.remove(room)

    def reload(self, graph: RoomGraph) -> None:
        """Swap in a re-read world, unloading every room and loading around the active one."""
        for name in list(self.loaded):
            self.unload(name)
        self.graph = graph
        if self.active is not None:
            self.enter(self.active)

    def _load(self, name: str) -> None:
        level = self.graph.levels[name]
        room = Room(level, level.layer(self.layer).to_tile_grid(self.legend))
        self.loaded[name] = room
        self.grid.add(room)
        if self.on_load is not None:
            self.on_load(room)
