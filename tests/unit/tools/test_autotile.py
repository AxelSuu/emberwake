from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame
import pytest
from tools.autotile.__main__ import main
from tools.autotile.blob import (
    COLUMNS,
    INDEX,
    MASKS,
    NE,
    NW,
    E,
    N,
    S,
    W,
    build,
    build_sheet,
    canonical,
    mask_at,
    rules,
    tile_for,
)

if TYPE_CHECKING:
    from pathlib import Path

SIZE = 4
FILL, EDGE, OUTER, INNER = (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)


def source() -> pygame.Surface:
    sheet = pygame.Surface((SIZE * 4, SIZE), pygame.SRCALPHA)
    for i, color in enumerate((FILL, EDGE, OUTER, INNER)):
        sheet.fill(color, (i * SIZE, 0, SIZE, SIZE))
    return sheet


def color_at(sheet: pygame.Surface, mask: int, x: int, y: int) -> tuple[int, int, int]:
    i = INDEX[mask]
    c = sheet.get_at((i % COLUMNS * SIZE + x, i // COLUMNS * SIZE + y))
    return (c.r, c.g, c.b)


def test_blob_has_47_tiles() -> None:
    assert len(MASKS) == 47


def test_canonical_drops_unsupported_corners() -> None:
    assert canonical(NE) == 0
    assert canonical(N | NE) == N
    assert canonical(N | E | NE) == N | E | NE


def test_mask_at() -> None:
    cells = {(0, 0), (1, 0), (0, 1)}
    assert mask_at(cells, 0, 0) == E | S
    assert mask_at(cells | {(1, 1)}, 0, 0) == E | S | 8
    assert tile_for(set(), 0, 0) == INDEX[0]


def test_isolated_and_interior_tiles() -> None:
    sheet = build_sheet(source())
    for x, y in ((0, 0), (3, 0), (0, 3), (3, 3)):
        assert color_at(sheet, 0, x, y) == OUTER
    interior = 255
    for x, y in ((0, 0), (3, 3), (1, 2)):
        assert color_at(sheet, interior, x, y) == FILL


def test_inner_corner_only_where_diagonal_is_missing() -> None:
    sheet = build_sheet(source())
    mask = 255 & ~NW
    assert color_at(sheet, mask, 0, 0) == INNER
    assert color_at(sheet, mask, 3, 3) == FILL


def test_edges_follow_open_side() -> None:
    sheet = build_sheet(source())
    top_open = canonical(255 & ~N)
    assert color_at(sheet, top_open, 0, 0) == EDGE
    assert color_at(sheet, top_open, 3, 0) == EDGE
    assert color_at(sheet, top_open, 0, 3) == FILL
    left_open = canonical(255 & ~W)
    assert color_at(sheet, left_open, 0, 3) == EDGE
    assert color_at(sheet, left_open, 3, 3) == FILL


def test_rules_cover_every_mask() -> None:
    out = rules()
    assert len(out) == 47
    assert all(r["pattern"][4] == 1 and len(r["pattern"]) == 9 for r in out)
    assert out[INDEX[0]]["pattern"] == [0, -1, 0, -1, 1, -1, 0, -1, 0]
    assert out[INDEX[255]]["pattern"] == [1] * 9


def test_bad_source_size(tmp_path: Path) -> None:
    pygame.image.save(pygame.Surface((10, 4)), tmp_path / "bad.png")
    with pytest.raises(ValueError, match="square tiles"):
        build(tmp_path / "bad.png", tmp_path)


def test_cli(tmp_path: Path) -> None:
    pygame.image.save(source(), tmp_path / "ground.png")
    assert main([str(tmp_path / "ground.png"), "--out", str(tmp_path / "out")]) == 0
    data = json.loads((tmp_path / "out" / "ground.rules.json").read_text())
    assert len(data["rules"]) == 47
    assert pygame.image.load(tmp_path / "out" / "ground.png").get_size() == (8 * SIZE, 6 * SIZE)
