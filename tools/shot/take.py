"""Run the gameplay scene without a window for a few ticks and save what it draws."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.app import CANVAS_SIZE
from emberwake.engine.core.events import EventBus
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.ldtk import load_project
from emberwake.game import paths
from emberwake.game.context import GameContext
from emberwake.game.data.settings import Settings
from emberwake.game.scenes.gameplay import WORLD, GameplayScene
from emberwake.game.strings import load_strings

if TYPE_CHECKING:
    from pathlib import Path

STEP = 1 / 60


def all_rooms() -> list[str]:
    return sorted(level.identifier for level in load_project(paths.levels(WORLD)).all_levels)


def _init() -> None:
    if not pygame.display.get_init():
        pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    pygame.font.init()


def shoot(
    room: str, out: Path, *, at: tuple[float, float] | None = None, ticks: int = 90, scale: int = 2
) -> Path:
    """Start in `room` (player feet at `at`, room px, if given), run `ticks` and save a frame."""
    _init()
    strings = load_strings("en")
    ctx = GameContext(MemoryStorage(), Settings(), EventBus(), CANVAS_SIZE, strings=strings)
    scenes = SceneManager()
    game = GameplayScene(ctx, room=room)
    scenes.push(game)
    scenes.update(STEP)
    if at is not None:
        rect = game.rooms.graph.rects[room]
        body = game.body
        body.x, body.y = rect.x + at[0] - body.width / 2, rect.y + at[1] - body.height
        game.motor.previous = (body.x, body.y)
        game.camera.snap(*game._camera_target())
    canvas = pygame.Surface(CANVAS_SIZE)
    for _ in range(ticks):
        scenes.update(STEP)
        scenes.draw(canvas, 1.0)
    while len(game.jobs):
        scenes.draw(canvas, 1.0)
    scenes.draw(canvas, 1.0)
    pygame.image.save(pygame.transform.scale_by(canvas, scale), out)
    return out
