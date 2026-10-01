from __future__ import annotations

import asyncio

import pygame
import pytest

from emberwake.app import CANVAS_SIZE
from emberwake.engine.core.events import EventBus
from emberwake.engine.platform.display import Display
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.runner import Runner
from emberwake.engine.scene import SceneManager
from emberwake.game.context import GameContext
from emberwake.game.data.settings import Settings
from emberwake.game.scenes.boot import BootScene
from emberwake.game.scenes.title import TitleScene

STEP = 1 / 60


@pytest.fixture
def display():
    pygame.init()
    yield Display(CANVAS_SIZE, "test", vsync=False)
    pygame.quit()


@pytest.fixture
def ctx(display: Display) -> GameContext:
    return GameContext(MemoryStorage(), Settings(), EventBus(), CANVAS_SIZE)


def test_boot_hands_over_to_title_and_title_renders(display: Display, ctx: GameContext):
    scenes = SceneManager()
    scenes.push(BootScene(ctx))
    for _ in range(int(3 / STEP)):
        scenes.update(STEP)
        scenes.draw(display.canvas, 0.0)
    assert isinstance(scenes.top, TitleScene)
    assert scenes.top.embers
    assert display.canvas.get_at((0, 0)) != pygame.Color(0, 0, 0)


def test_escape_on_title_ends_the_loop(display: Display, ctx: GameContext):
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    pygame.event.post(pygame.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    runner = Runner(display, scenes, max_frames=100)
    asyncio.run(runner.run())
    assert not scenes
