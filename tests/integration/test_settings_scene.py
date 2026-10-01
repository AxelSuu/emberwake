"""The settings overlay changes settings live, saves them and keeps the language live."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.render.frame import Flag
from emberwake.engine.scene import SceneManager
from emberwake.engine.ui import ScrollList, Slider, Toggle
from emberwake.game.data.settings import SETTINGS_KEY
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.settings import SettingsScene

if TYPE_CHECKING:
    from emberwake.engine.ui import Widget
    from emberwake.game.context import GameContext


def press(scenes: SceneManager, key: int) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    scenes.update(1 / 60)


def inner(scene: SettingsScene) -> ScrollList:
    found = scene.ui.root.children[1]
    assert isinstance(found, ScrollList)
    return found


def rows(scene: SettingsScene) -> list[Widget]:
    return inner(scene).children


def labelled(scene: SettingsScene, text: str) -> Widget:
    return next(row for row in rows(scene) if row.focusable and getattr(row, "text", "") == text)


def focus(scenes: SceneManager, scene: SettingsScene, target: Widget) -> None:
    """Move focus to `target` with up or down presses."""
    for _ in range(len(rows(scene))):
        index = inner(scene).index
        goal = rows(scene).index(target)
        if index == goal:
            return
        press(scenes, pygame.K_DOWN if goal > index else pygame.K_UP)
    msg = "focus never reached the widget"
    raise AssertionError(msg)


def open_settings(ctx: GameContext) -> tuple[SceneManager, SettingsScene]:
    scenes = SceneManager()
    scene = SettingsScene(ctx)
    scenes.push(scene)
    scenes.update(1 / 60)
    return scenes, scene


def test_toggles_and_sliders_change_the_settings_as_they_are_used(ctx: GameContext):
    scenes, scene = open_settings(ctx)
    assert ctx.settings.video.crt is False
    crt = labelled(scene, "CRT lines")
    assert isinstance(crt, Toggle)
    focus(scenes, scene, crt)
    press(scenes, pygame.K_RETURN)
    assert ctx.settings.video.crt is True
    shake = labelled(scene, "Screen shake")
    assert isinstance(shake, Slider)
    focus(scenes, scene, shake)
    press(scenes, pygame.K_LEFT)
    assert ctx.settings.video.screen_shake == 0.9


def test_leaving_saves_to_settings_json(ctx: GameContext):
    assert isinstance(ctx.storage, MemoryStorage)
    scenes, _ = open_settings(ctx)
    ctx.settings.audio.music = 0.3
    press(scenes, pygame.K_ESCAPE)
    assert scenes.top is None
    saved = json.loads(ctx.storage.read(SETTINGS_KEY) or "{}")
    assert saved["data"]["audio"]["music"] == 0.3


def test_language_switches_live_and_is_remembered(ctx: GameContext):
    scenes, scene = open_settings(ctx)
    selector = labelled(scene, "Language")
    focus(scenes, scene, selector)
    press(scenes, pygame.K_RIGHT)
    assert ctx.settings.language == "sv"
    assert ctx.t("settings.title") == "Inställningar"
    scene_texts = [getattr(row, "text", "") for row in rows(scene)]
    assert "Helskärm" in scene_texts
    assert inner(scene).current is not None


def test_back_button_closes(ctx: GameContext):
    scenes, scene = open_settings(ctx)
    press(scenes, pygame.K_UP)
    assert scene.ui.root.current is scene.ui.root.children[2]
    press(scenes, pygame.K_RETURN)
    assert scenes.top is None


def test_gameplay_picks_up_changed_settings_when_the_overlay_closes(ctx: GameContext):
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Test_Room")
    scenes.push(game)
    scenes.update(1 / 60)
    assert Flag.CRT not in game.frame.flags
    scenes.push(SettingsScene(ctx))
    scenes.update(1 / 60)
    ctx.settings.video.crt = True
    ctx.settings.video.screen_shake = 0.0
    ctx.settings.accessibility.reduce_flashes = True
    press(scenes, pygame.K_ESCAPE)
    assert Flag.CRT in game.frame.flags
    assert game.camera.shake.intensity == 0.0
    game.flash.start(1.0)
    assert game.flash.left == 0.0
