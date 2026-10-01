from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest
from tools.normals.__main__ import main
from tools.normals.generate import bevel, generate, generate_file

if TYPE_CHECKING:
    from pathlib import Path


def block(path: Path, size: int = 9, color: tuple[int, ...] = (200, 50, 50, 255)) -> Path:
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    surface.fill(color)
    pygame.image.save(surface, path)
    return path


def test_bevel_rises_from_edge() -> None:
    field = bevel([[True] * 9 for _ in range(9)], 3)
    assert field[0][4] < field[1][4] < field[2][4] <= field[4][4] == 1.0


def test_bevel_treats_transparent_as_zero() -> None:
    field = bevel([[False, True, True], [False, True, True], [False, True, True]], 2)
    assert field[1][0] == 0.0
    assert field[1][1] > 0.0


def test_edges_tilt_outward_and_center_is_flat(tmp_path: Path) -> None:
    out = pygame.image.load(generate_file(block(tmp_path / "a.png")))
    assert tuple(out.get_at((4, 4))) == (128, 128, 255, 255)
    assert out.get_at((0, 4)).r < 128
    assert out.get_at((8, 4)).r > 128
    assert out.get_at((4, 0)).g > 128
    assert out.get_at((4, 8)).g < 128


def test_transparent_pixels_stay_transparent(tmp_path: Path) -> None:
    surface = pygame.Surface((5, 5), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    surface.set_at((2, 2), (255, 255, 255, 255))
    pygame.image.save(surface, tmp_path / "dot.png")
    out = pygame.image.load(generate_file(tmp_path / "dot.png"))
    assert out.get_at((0, 0)).a == 0


def test_height_layer_adds_relief(tmp_path: Path) -> None:
    source = block(tmp_path / "a.png", 7)
    flat = pygame.image.load(generate_file(source)).get_at((3, 3))
    layer = pygame.Surface((7, 7), pygame.SRCALPHA)
    layer.fill((0, 0, 0, 255))
    for y in range(7):
        layer.set_at((4, y), (255, 255, 255, 255))
    pygame.image.save(layer, tmp_path / "a_h.png")
    raised = pygame.image.load(generate_file(source)).get_at((3, 3))
    assert raised.r < flat.r


def test_height_size_mismatch(tmp_path: Path) -> None:
    source = block(tmp_path / "a.png")
    block(tmp_path / "a_h.png", 4)
    with pytest.raises(ValueError, match="expected"):
        generate_file(source)


def test_generate_skips_derived_and_is_stable(tmp_path: Path) -> None:
    block(tmp_path / "a.png")
    first = generate(tmp_path)
    data = first[0].read_bytes()
    assert len(generate(tmp_path)) == 1
    assert first[0].read_bytes() == data


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    block(tmp_path / "a.png")
    assert main(["--assets", str(tmp_path)]) == 0
    assert "1 normal maps" in capsys.readouterr().out
