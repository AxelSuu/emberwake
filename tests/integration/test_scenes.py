from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.runner import Runner
from emberwake.engine.scene import SceneManager
from emberwake.game.scenes.boot import BootScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.title import TitleScene

if TYPE_CHECKING:
    from emberwake.engine.platform.display import Display
    from emberwake.game.context import GameContext

STEP = 1 / 60


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


def test_any_key_on_title_starts_gameplay_and_escape_returns(ctx: GameContext):
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    scenes.apply_pending()
    scenes.handle(pygame.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
    scenes.update(STEP)
    assert isinstance(scenes.top, GameplayScene)
    scenes.handle(pygame.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    scenes.update(STEP)
    assert isinstance(scenes.top, TitleScene)
