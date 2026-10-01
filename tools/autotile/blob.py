"""47-tile blob autotiling: neighbour masks, a sheet built from four source tiles, LDtk rules."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from pathlib import Path

N, NE, E, SE, S, SW, W, NW = 1, 2, 4, 8, 16, 32, 64, 128
OFFSETS = {
    N: (0, -1),
    NE: (1, -1),
    E: (1, 0),
    SE: (1, 1),
    S: (0, 1),
    SW: (-1, 1),
    W: (-1, 0),
    NW: (-1, -1),
}
CORNERS = {NE: N | E, SE: S | E, SW: S | W, NW: N | W}
COLUMNS = 8
SOURCE_TILES = ("fill", "edge", "outer", "inner")


def canonical(mask: int) -> int:
    """Drop corner bits whose neighbouring edges are not both set; they cannot change the look."""
    for corner, edges in CORNERS.items():
        if mask & edges != edges:
            mask &= ~corner
    return mask


MASKS: tuple[int, ...] = tuple(sorted({canonical(m) for m in range(256)}))
INDEX = {mask: i for i, mask in enumerate(MASKS)}


def mask_at(solid: set[tuple[int, int]], x: int, y: int) -> int:
    """Canonical mask of the cell (x, y) against a set of solid cells."""
    mask = sum(bit for bit, (dx, dy) in OFFSETS.items() if (x + dx, y + dy) in solid)
    return canonical(mask)


def tile_for(solid: set[tuple[int, int]], x: int, y: int) -> int:
    return INDEX[mask_at(solid, x, y)]


def quadrant_kind(vertical: bool, horizontal: bool, diagonal: bool) -> str:
    """Which source tile a quadrant copies, given its three neighbours."""
    if vertical and horizontal:
        return "fill" if diagonal else "inner"
    if horizontal:
        return "edge"
    if vertical:
        return "edge_side"
    return "outer"


def split_source(sheet: pygame.Surface) -> tuple[dict[str, pygame.Surface], int]:
    """The four source tiles from a one-row sheet (fill, edge, outer, inner), and the tile size."""
    size = sheet.get_height()
    if sheet.get_width() != size * len(SOURCE_TILES):
        raise ValueError(f"source must be {len(SOURCE_TILES)} square tiles in a row")
    tiles = {}
    for i, name in enumerate(SOURCE_TILES):
        tile = pygame.Surface((size, size), pygame.SRCALPHA)
        tile.blit(sheet, (0, 0), (i * size, 0, size, size))
        tiles[name] = tile
    tiles["edge_side"] = pygame.transform.rotate(tiles["edge"], 90)
    return tiles, size


def compose(mask: int, tiles: dict[str, pygame.Surface], size: int) -> pygame.Surface:
    """One tile for `mask`: each quadrant is the mirrored corner of the matching source tile."""
    half = size // 2
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    for corner, (vertical, horizontal, flip_x, flip_y) in {
        NW: (N, W, False, False),
        NE: (N, E, True, False),
        SW: (S, W, False, True),
        SE: (S, E, True, True),
    }.items():
        kind = quadrant_kind(bool(mask & vertical), bool(mask & horizontal), bool(mask & corner))
        source = pygame.transform.flip(tiles[kind], flip_x, flip_y)
        x, y = (half if flip_x else 0), (half if flip_y else 0)
        out.blit(source, (x, y), (x, y, half, half))
    return out


def build_sheet(source: pygame.Surface) -> pygame.Surface:
    """The 47-tile sheet (8 columns, mask order) from a four-tile source row."""
    tiles, size = split_source(source)
    rows = -(-len(MASKS) // COLUMNS)
    sheet = pygame.Surface((COLUMNS * size, rows * size), pygame.SRCALPHA)
    for i, mask in enumerate(MASKS):
        sheet.blit(compose(mask, tiles, size), (i % COLUMNS * size, i // COLUMNS * size))
    return sheet


def rules() -> list[dict]:
    """LDtk auto-layer rules: a 3x3 pattern per mask (1 solid, -1 empty, 0 either) to a tile id."""
    out = []
    for mask in MASKS:
        pattern = [0] * 9
        for bit, (dx, dy) in OFFSETS.items():
            edges = CORNERS.get(bit)
            if edges is not None and mask & edges != edges:
                continue
            pattern[(dy + 1) * 3 + dx + 1] = 1 if mask & bit else -1
        pattern[4] = 1
        out.append({"size": 3, "pattern": pattern, "tileIds": [INDEX[mask]], "chance": 1.0})
    return out


def build(source: Path, out: Path) -> tuple[Path, Path]:
    """Write ``<name>.png`` (47-tile sheet) and ``<name>.rules.json`` next to each other."""
    image = pygame.image.load(source)
    surface = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    surface.blit(image, (0, 0))
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"{source.stem}.png"
    pygame.image.save(build_sheet(surface), png)
    rules_path = out / f"{source.stem}.rules.json"
    rules_path.write_text(json.dumps({"columns": COLUMNS, "rules": rules()}, indent=1) + "\n")
    return png, rules_path
