"""Move axis-aligned bodies through a `TileSource`.

Movement is resolved one axis at a time (x, then y) and split into sub-steps of at most half a
tile, so only the leading row or column needs testing and nothing tunnels through thin walls.
Bodies are assumed not to overlap solid tiles when a move starts. Boxes passed as `solids` (crates,
say) block like solid tiles, though they have no cells.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.ecs import component
from emberwake.engine.physics.tiles import Tile

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from emberwake.engine.physics.tiles import TileSource

EPSILON = 1e-6
SOLID_ONLY = frozenset({Tile.SOLID})


@component
@dataclass(slots=True)
class Body:
    """An axis-aligned box; ``x``/``y`` is its top-left corner in pixels."""

    x: float
    y: float
    width: float
    height: float

    @property
    def bottom(self) -> float:
        """Y coordinate of the bottom edge."""
        return self.y + self.height

    @property
    def center_x(self) -> float:
        """X coordinate of the centre."""
        return self.x + self.width / 2


@dataclass(slots=True)
class Contacts:
    """Which sides of a body hit something during a move."""

    ground: bool = False
    ceiling: bool = False
    left: bool = False
    right: bool = False
    one_way: bool = False
    """Landed on one-way platforms only (no solid tile underneath)."""


def _meets(body: Body, x: float, y: float, width: float, height: float) -> bool:
    return (
        x < body.x + body.width - EPSILON
        and body.x < x + width - EPSILON
        and y < body.bottom - EPSILON
        and body.y < y + height - EPSILON
    )


def overlaps(
    grid: TileSource,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    kinds: Collection[Tile] = SOLID_ONLY,
    solids: Sequence[Body] = (),
) -> bool:
    """Whether the box touches any tile whose kind is in `kinds`, or any of the `solids`."""
    if any(_meets(solid, x, y, width, height) for solid in solids):
        return True
    size = grid.tile_size
    for row in range(math.floor(y / size), math.floor((y + height - EPSILON) / size) + 1):
        for column in range(math.floor(x / size), math.floor((x + width - EPSILON) / size) + 1):
            if grid.get(column, row) in kinds:
                return True
    return False


def move(
    grid: TileSource,
    body: Body,
    dx: float,
    dy: float,
    *,
    drop_through: bool = False,
    solids: Sequence[Body] = (),
) -> Contacts:
    """Move `body` by (`dx`, `dy`) pixels, stopping at tiles. Mutates `body`.

    Args:
        grid: The collision grid.
        body: The body to move.
        dx: Horizontal distance.
        dy: Vertical distance (positive is down).
        drop_through: Ignore one-way platforms, for dropping down through them.
        solids: Boxes that block like solid tiles from every side. `body` itself is skipped.

    Returns:
        The contacts made. Velocity is the caller's business: zero it on contact if needed.
    """
    contacts = Contacts()
    steps = max(1, math.ceil(max(abs(dx), abs(dy)) / (grid.tile_size / 2)))
    step_x, step_y = dx / steps, dy / steps
    for _ in range(steps):
        if step_x and _step_x(grid, body, step_x, contacts, solids):
            step_x = 0.0
        if step_y and _step_y(grid, body, step_y, contacts, solids, drop_through=drop_through):
            step_y = 0.0
    return contacts


def _rows(grid: TileSource, body: Body) -> range:
    size = grid.tile_size
    return range(math.floor(body.y / size), math.floor((body.bottom - EPSILON) / size) + 1)


def _columns(grid: TileSource, body: Body) -> range:
    size = grid.tile_size
    return range(math.floor(body.x / size), math.floor((body.x + body.width - EPSILON) / size) + 1)


def _step_x(
    grid: TileSource, body: Body, distance: float, contacts: Contacts, solids: Sequence[Body]
) -> bool:
    size = grid.tile_size
    new_x = body.x + distance
    if distance > 0:
        column = math.floor((new_x + body.width - EPSILON) / size)
        if any(grid.get(column, row) is Tile.SOLID for row in _rows(grid, body)):
            body.x = column * size - body.width
            contacts.right = True
            return True
    else:
        column = math.floor(new_x / size)
        if any(grid.get(column, row) is Tile.SOLID for row in _rows(grid, body)):
            body.x = (column + 1) * size
            contacts.left = True
            return True
    for solid in solids:
        if solid is not body and _meets(solid, new_x, body.y, body.width, body.height):
            if distance > 0:
                body.x = solid.x - body.width
                contacts.right = True
            else:
                body.x = solid.x + solid.width
                contacts.left = True
            return True
    body.x = new_x
    return False


def _step_y(
    grid: TileSource,
    body: Body,
    distance: float,
    contacts: Contacts,
    solids: Sequence[Body],
    *,
    drop_through: bool,
) -> bool:
    size = grid.tile_size
    new_y = body.y + distance
    if distance > 0:
        row = math.floor((new_y + body.height - EPSILON) / size)
        tiles = {grid.get(column, row) for column in _columns(grid, body)}
        was_above = body.bottom <= row * size + EPSILON
        lands_on_one_way = Tile.ONE_WAY in tiles and was_above and not drop_through
        if Tile.SOLID in tiles or lands_on_one_way:
            body.y = row * size - body.height
            contacts.ground = True
            contacts.one_way = Tile.SOLID not in tiles
            return True
    else:
        row = math.floor(new_y / size)
        if any(grid.get(column, row) is Tile.SOLID for column in _columns(grid, body)):
            body.y = (row + 1) * size
            contacts.ceiling = True
            return True
    for solid in solids:
        if solid is body or not _meets(solid, body.x, new_y, body.width, body.height):
            continue
        if distance > 0 and body.bottom <= solid.y + EPSILON:
            body.y = solid.y - body.height
            contacts.ground, contacts.one_way = True, False
            return True
        if distance < 0 and body.y >= solid.bottom - EPSILON:
            body.y = solid.bottom
            contacts.ceiling = True
            return True
    body.y = new_y
    return False
