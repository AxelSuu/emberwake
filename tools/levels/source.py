"""Read the text level source: entity definitions, room placement, ASCII rooms and their TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path

GRID = 16
WORLD_CELL = (20, 11)
"""GridVania cell in tiles (320x176 px). Room sizes and positions are whole cells."""

TILES = {"#": 1, "=": 2, "^": 3}
"""ASCII tile -> Collisions IntGrid value."""
EMPTY = frozenset(".")
DEFAULT_MARKERS = {"P": "PlayerStart"}
"""Markers that need no entry in the room's TOML."""

type FieldType = Literal["Bool", "Int", "Float", "String", "EntityRef"]


class SourceError(ValueError):
    """The level source is inconsistent; the message says where."""


@dataclass(slots=True)
class FieldSpec:
    type: FieldType
    array: bool = False
    default: Any = None
    doc: str | None = None


@dataclass(slots=True)
class EntitySpec:
    color: str
    size: tuple[int, int] = (GRID, GRID)
    pivot: tuple[float, float] = (0.5, 1.0)
    resizable: bool = False
    max_count: int = 0
    """Per level; 0 is unlimited."""
    doc: str | None = None
    fields: dict[str, FieldSpec] = field(default_factory=dict)


@dataclass(slots=True)
class Defs:
    """``defs.toml``: every entity type and level field the generated project defines."""

    level_fields: dict[str, FieldSpec] = field(default_factory=dict)
    entities: dict[str, EntitySpec] = field(default_factory=dict)


@dataclass(slots=True)
class Placement:
    cell: tuple[int, int]
    """World grid cell of the room's top-left corner."""


@dataclass(slots=True)
class WorldFile:
    """``world.toml``: which rooms exist and where they sit."""

    rooms: dict[str, Placement] = field(default_factory=dict)


@dataclass(slots=True)
class MarkerSpec:
    type: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RoomFile:
    """``<room>.toml``: level fields and what each marker character is."""

    fields: dict[str, Any] = field(default_factory=dict)
    entities: dict[str, MarkerSpec] = field(default_factory=dict)


@dataclass(slots=True)
class Placed:
    """One entity: a marker's connected block of cells, in tiles."""

    marker: str
    type: str
    column: int
    row: int
    columns: int
    rows: int
    fields: dict[str, Any]
    index: int = 0
    """Position among the room's blocks of the same marker, in reading order."""
    count: int = 1
    """How many blocks that marker has in the room."""


@dataclass(slots=True)
class Room:
    name: str
    cell: tuple[int, int]
    rows: list[str]
    fields: dict[str, Any]
    entities: list[Placed]

    @property
    def size(self) -> tuple[int, int]:
        """Width and height in tiles."""
        return len(self.rows[0]), len(self.rows)

    @property
    def world_px(self) -> tuple[int, int]:
        return self.cell[0] * WORLD_CELL[0] * GRID, self.cell[1] * WORLD_CELL[1] * GRID


@dataclass(slots=True)
class Source:
    defs: Defs
    rooms: list[Room]


def read_toml[T](tp: type[T], path: Path) -> T:
    try:
        return from_data(tp, tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValueError) as error:
        raise SourceError(f"{path}: {error}") from None


def load_source(directory: Path) -> Source:
    """Read ``defs.toml``, ``world.toml`` and every room it lists from `directory`."""
    defs = read_toml(Defs, directory / "defs.toml")
    world = read_toml(WorldFile, directory / "world.toml")
    rooms = []
    for name, placement in world.rooms.items():
        stem = directory / name.lower()
        toml = stem.with_suffix(".toml")
        room_file = read_toml(RoomFile, toml) if toml.exists() else RoomFile()
        text = stem.with_suffix(".txt").read_text(encoding="utf-8")
        rooms.append(make_room(name, placement.cell, text, room_file))
    check_layout(rooms)
    return Source(defs, rooms)


def make_room(
    name: str, cell: tuple[int, int], text: str, room_file: RoomFile | None = None
) -> Room:
    """A room from its ASCII map and parsed TOML."""
    room_file = room_file or RoomFile()
    rows = parse_rows(text, name)
    return Room(name, cell, rows, room_file.fields, place(rows, room_file, name))


def parse_rows(text: str, room: str) -> list[str]:
    rows = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise SourceError(f"{room}: rows must be non-empty and of equal length")
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char not in TILES and char not in EMPTY and not char.isalnum():
                raise SourceError(f"{room} ({x}, {y}): unknown character {char!r}")
    width, height = len(rows[0]), len(rows)
    if width % WORLD_CELL[0] or height % WORLD_CELL[1]:
        msg = f"{room}: {width}x{height} tiles is not a whole number of {WORLD_CELL} cells"
        raise SourceError(msg)
    return rows


def place(rows: list[str], room_file: RoomFile, room: str) -> list[Placed]:
    """Turn marker characters into entities: each 4-connected block of one marker is one."""
    blocks: dict[str, list[tuple[int, int, int, int]]] = {}
    seen: set[tuple[int, int]] = set()
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char.isalnum() and (x, y) not in seen:
                blocks.setdefault(char, []).append(_block(rows, x, y, seen, room))
    placed = []
    for marker, rects in blocks.items():
        spec = room_file.entities.get(marker)
        if spec is None and marker in DEFAULT_MARKERS:
            spec = MarkerSpec(DEFAULT_MARKERS[marker])
        if spec is None:
            raise SourceError(f"{room}: marker {marker!r} has no [entities.{marker}] entry")
        for index, (x, y, w, h) in enumerate(rects):
            placed.append(Placed(marker, spec.type, x, y, w, h, spec.fields, index, len(rects)))
    unused = room_file.entities.keys() - blocks.keys()
    if unused:
        raise SourceError(f"{room}: markers {sorted(unused)} are defined but not in the map")
    return sorted(placed, key=lambda p: (p.row, p.column))


def _block(
    rows: list[str], x: int, y: int, seen: set[tuple[int, int]], room: str
) -> tuple[int, int, int, int]:
    marker = rows[y][x]
    stack, cells = [(x, y)], []
    seen.add((x, y))
    while stack:
        cx, cy = stack.pop()
        cells.append((cx, cy))
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            inside = 0 <= ny < len(rows) and 0 <= nx < len(rows[0])
            if inside and (nx, ny) not in seen and rows[ny][nx] == marker:
                seen.add((nx, ny))
                stack.append((nx, ny))
    left, top = min(c[0] for c in cells), min(c[1] for c in cells)
    w = max(c[0] for c in cells) - left + 1
    h = max(c[1] for c in cells) - top + 1
    if len(cells) != w * h:
        raise SourceError(f"{room} ({left}, {top}): marker {marker!r} block is not a rectangle")
    return left, top, w, h


def check_layout(rooms: list[Room]) -> None:
    """Rooms must not overlap in the world."""
    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            if _overlap(_cells(a), _cells(b)):
                raise SourceError(f"rooms {a.name} and {b.name} overlap")


def _cells(room: Room) -> tuple[int, int, int, int]:
    width, height = room.size
    return room.cell[0], room.cell[1], width // WORLD_CELL[0], height // WORLD_CELL[1]


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
