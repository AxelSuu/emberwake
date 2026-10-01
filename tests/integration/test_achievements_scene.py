"""Achievements unlock during play, toast, persist, and show on the achievements screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import SceneManager
from emberwake.game import paths
from emberwake.game.achievements import ACHIEVEMENTS_KEY, Achievements, load_defs
from emberwake.game.interact import Collected
from emberwake.game.scenes.achievements import AchievementsScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.menu import MenuScene
from emberwake.game.scenes.title import TitleScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def armed(ctx: GameContext) -> GameContext:
    ctx.achievements = Achievements.load(load_defs(paths.content("achievements.toml")), ctx.storage)
    return ctx


def test_playing_unlocks_toasts_and_saves(ctx: GameContext) -> None:
    armed(ctx)
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Test_Room")
    scenes.push(game)
    scenes.update(STEP)
    ctx.bus.publish(Collected("e", 30))
    assert ctx.achievements.unlocked("ember_collector")
    assert len(game.toasts) >= 1
    assert "ember_collector" in (ctx.storage.read(ACHIEVEMENTS_KEY) or "")
    for _ in range(round(4 / STEP)):
        scenes.update(STEP)
    assert len(game.toasts) == 0


def test_entering_the_first_room_counts(ctx: GameContext) -> None:
    armed(ctx)
    scenes = SceneManager()
    scenes.push(GameplayScene(ctx, room="Test_Room"))
    scenes.update(STEP)
    assert ctx.achievements.data.rooms == ["Test_Room"]


def test_the_screen_lists_progress(ctx: GameContext) -> None:
    armed(ctx)
    ctx.achievements.record("Jumped", 40)
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    scenes.update(STEP)
    assert isinstance(scenes.top, MenuScene)
    scene = AchievementsScene(ctx)
    texts = [getattr(row, "text", "") for row in scene.rows]
    assert any("Jumps: 40" in t for t in texts)
    assert any("Leaper" in t and "40/100" in t for t in texts)
    assert any("First steps" in t and "[x]" in t for t in texts)


def test_the_menu_opens_the_screen(ctx: GameContext) -> None:
    armed(ctx)
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    scenes.update(STEP)
    menu = scenes.top
    assert isinstance(menu, MenuScene)
    for _ in range(8):
        current = menu.ui.root.current
        if current is not None and current.text == "Achievements":
            break
        scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    scenes.update(STEP)
    assert isinstance(scenes.top, AchievementsScene)
