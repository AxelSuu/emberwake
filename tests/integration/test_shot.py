from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from tools.shot.take import all_rooms, shoot

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.engine.platform.display import Display


def test_a_room_is_shot_at_the_given_spot(tmp_path: Path, display: Display) -> None:
    out = shoot("Lever_Hall", tmp_path / "shot.png", at=(60, 120), ticks=2, scale=1)
    assert pygame.image.load(out).get_size() == (640, 360)
    assert "Lever_Hall" in all_rooms()
