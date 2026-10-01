from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.runner import Runner
from emberwake.engine.scene import SceneManager
from emberwake.game.scenes.boot import BootScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.menu import MenuScene
from emberwake.game.scenes.pause import PauseScene
from emberwake.game.scenes.settings import SettingsScene
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


def key(scenes: SceneManager, code: int) -> None:
    scenes.handle(pygame.Event(pygame.KEYDOWN, key=code, mod=0))
    scenes.update(STEP)


def test_any_key_on_title_opens_the_menu(ctx: GameContext):
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    scenes.apply_pending()
    key(scenes, pygame.K_SPACE)
    assert isinstance(scenes.top, MenuScene)


def test_escape_pauses_gameplay_and_escape_again_resumes(ctx: GameContext):
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.update(STEP)
    key(scenes, pygame.K_ESCAPE)
    assert isinstance(scenes.top, PauseScene)
    clock = game.clock
    scenes.update(STEP)
    assert game.clock == clock
    key(scenes, pygame.K_ESCAPE)
    assert scenes.top is game
    scenes.update(STEP)
    assert game.clock > clock


def test_pause_menu_opens_settings_and_quits_to_title(ctx: GameContext):
    scenes = SceneManager()
    scenes.push(GameplayScene(ctx))
    scenes.update(STEP)
    key(scenes, pygame.K_ESCAPE)
    key(scenes, pygame.K_DOWN)
    key(scenes, pygame.K_DOWN)
    key(scenes, pygame.K_RETURN)
    assert isinstance(scenes.top, SettingsScene)
    key(scenes, pygame.K_ESCAPE)
    assert isinstance(scenes.top, PauseScene)
    key(scenes, pygame.K_DOWN)
    key(scenes, pygame.K_RETURN)
    assert isinstance(scenes.top, TitleScene)
    assert len(scenes.scenes) == 1
