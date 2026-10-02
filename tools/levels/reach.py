"""Where the player can get on a tile map: a generous model of walking, jumping and the dash."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.physics import Tile

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

type Cell = tuple[int, int]

OPEN = (Tile.EMPTY, Tile.ONE_WAY)
"""Tiles the player's body can be in; hazards and the void (missing cells) are not."""


@dataclass(frozen=True, slots=True)
class Moves:
    """Tiles the player can rise and cross in one jump, and again after touching a wall."""

    up: int = 3
    across: int = 6
    wall_up: int = 3
    wall_across: int = 2
    shaft: int = 6
    """Widest gap between two walls that can be climbed by jumping from one to the other."""

    def with_abilities(self, abilities: Collection[str]) -> Moves:
        """These moves widened by what the abilities add."""
        if "dash" in abilities:
            return Moves(self.up + 2, self.across + 4, self.wall_up, self.wall_across, self.shaft)
        return self


def reach(
    tiles: Mapping[Cell, Tile], starts: Iterable[Cell], moves: Moves | None = None
) -> set[Cell]:
    """Every cell the player's feet or head can be in, from standing on any of `starts`.

    The body is two tiles tall, so a cell is open only with the cell above it. Jumps are searched
    cell by cell, so walls and ceilings count; landing refills the jump, and so does a wall with
    another across the shaft.
    """
    moves = moves or Moves()
    solid = {cell for cell, tile in tiles.items() if tile == Tile.SOLID}
    oneway = {cell for cell, tile in tiles.items() if tile == Tile.ONE_WAY}
    empty = {cell for cell, tile in tiles.items() if tile in OPEN}
    free = {(x, y) for x, y in empty if (x, y - 1) in empty}
    full = moves.up, moves.across
    shaft = range(1, moves.shaft + 1)

    best: dict[Cell, list[tuple[int, int, bool]]] = {}
    seen: set[Cell] = set()
    stack = [(x, y, *full, False) for x, y in starts]
    while stack:
        x, y, up, across, fell = stack.pop()
        marks = best.setdefault((x, y), [])
        if any(u >= up and a >= across and (fell or not f) for u, a, f in marks):
            continue
        marks.append((up, across, fell))
        seen.update(((x, y), (x, y - 1)))
        beneath = x, y + 1
        if beneath in solid or beneath in oneway:
            stack.append((x, y, *full, False))
            if beneath in oneway and beneath in free:
                stack.append((x, y + 1, 0, across, True))
            for step in (-1, 1):
                ahead = x + step, y
                if ahead in free:
                    grounded = (x + step, y + 1) in solid or (x + step, y + 1) in oneway
                    stack.append((*ahead, *full, False) if grounded else (*ahead, 0, full[1], True))
        elif beneath in free and beneath in empty and tiles[beneath] == Tile.EMPTY:
            stack.append((x, y + 1, 0, across, True))
        if not fell and up and (x, y - 1) in free:
            stack.append((x, y - 1, up - 1, across, False))
        for step in (-1, 1):
            if (x + step, y) in solid:
                if any((x - step * k, y) in solid for k in shaft):
                    stack.append((x, y, moves.wall_up, max(across, moves.wall_across), False))
            elif across and (x + step, y) in free:
                stack.append((x + step, y, up, across - 1, fell))
    return seen
