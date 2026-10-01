"""Grid of collision tiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class Tile(IntEnum):
    """Collision kind of one grid cell."""

    EMPTY = 0
    SOLID = 1
    ONE_WAY = 2
    """Solid only for bodies landing on it from above."""
    HAZARD = 3
    """Passable, but kills on touch."""


class TileSource(Protocol):
    """Anything bodies can collide with: a single `TileGrid` or a world of rooms."""

    @property
    def tile_size(self) -> int:
        """Cell size in pixels."""
        ...

    def get(self, column: int, row: int) -> Tile:
        """Tile at a cell."""
        ...

    def void(self, x: float, y: float) -> bool:
        """Whether the point is in the void below the world, where bodies die."""
        ...


@dataclass(slots=True)
class TileGrid:
    """A ``width`` x ``height`` grid of `Tile` values stored row by row.

    Attributes:
        outside: Tile reported for coordinates outside the grid.
    """

    width: int
    height: int
    tile_size: int
    cells: bytearray
    outside: Tile = Tile.EMPTY

    def __post_init__(self) -> None:
        if len(self.cells) != self.width * self.height:
            msg = f"expected {self.width * self.height} cells, got {len(self.cells)}"
            raise ValueError(msg)

    @classmethod
    def from_rows(
        cls, rows: Sequence[str], legend: Mapping[str, Tile], tile_size: int = 16
    ) -> TileGrid:
        """Build a grid from equal-length strings; characters missing from `legend` are empty."""
        width = len(rows[0]) if rows else 0
        if any(len(row) != width for row in rows):
            msg = "rows must have equal length"
            raise ValueError(msg)
        cells = bytearray(legend.get(char, Tile.EMPTY) for row in rows for char in row)
        return cls(width, len(rows), tile_size, cells)

    @property
    def pixel_size(self) -> tuple[int, int]:
        """Grid size in pixels."""
        return self.width * self.tile_size, self.height * self.tile_size

    def get(self, column: int, row: int) -> Tile:
        """Tile at a cell, or `outside` beyond the edges."""
        if 0 <= column < self.width and 0 <= row < self.height:
            return Tile(self.cells[row * self.width + column])
        return self.outside

    def void(self, x: float, y: float) -> bool:
        """Whether `y` is below the bottom edge of the grid."""
        return y > self.height * self.tile_size

    def set(self, column: int, row: int, tile: Tile) -> None:
        """Change one cell."""
        self.cells[row * self.width + column] = tile
