from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame
import pytest

from emberwake.game.render.bank import SpriteBank

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def display():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.display.quit()


def sheet(root: Path, name: str, colors: list[str], ms: list[int] | None = None) -> None:
    image = pygame.Surface((4 * len(colors), 6), pygame.SRCALPHA)
    for i, color in enumerate(colors):
        image.fill(color, (i * 4, 0, 4, 6))
    root.mkdir(parents=True, exist_ok=True)
    pygame.image.save(image, root / f"{name}.png")
    if ms is not None:
        info = {"frame": [4, 6], "frames": len(colors), "ms": ms}
        (root / f"{name}.json").write_text(json.dumps(info))


def test_a_missing_sprite_is_none_so_the_placeholder_shows(tmp_path: Path) -> None:
    assert SpriteBank(tmp_path).image("clockrat") is None
    assert SpriteBank(None).image("clockrat") is None


def test_a_single_image_is_its_own_frame(tmp_path: Path) -> None:
    sheet(tmp_path, "lever", ["#f9c22b"])
    image = SpriteBank(tmp_path).image("lever")
    assert image is not None
    assert image.get_size() == (4, 6)


def test_frames_loop_on_their_timings(tmp_path: Path) -> None:
    sheet(tmp_path, "flame", ["#f9c22b", "#fb6b1d"], ms=[100, 300])
    bank = SpriteBank(tmp_path)
    images = [bank.image("flame", t) for t in (0.05, 0.2, 0.45)]
    colors = [image.get_at((0, 0))[:3] for image in images if image is not None]
    assert colors == [(249, 194, 43), (251, 107, 29), (249, 194, 43)]


def test_reload_picks_up_new_art(tmp_path: Path) -> None:
    bank = SpriteBank(tmp_path)
    assert bank.image("door") is None
    sheet(tmp_path, "door", ["#966c6c"])
    assert bank.image("door") is None
    bank.reload()
    assert bank.image("door") is not None
