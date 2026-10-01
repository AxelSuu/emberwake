"""The controls overlay rebinds live, reports conflicts, resets and persists."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import SceneManager
from emberwake.engine.ui import KeybindField, ScrollList
from emberwake.game.actions import Action, default_bindings
from emberwake.game.data.settings import SETTINGS_KEY
from emberwake.game.scenes.controls import ControlsScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.settings import SettingsScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


def press(scenes: SceneManager, key: int) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    scenes.update(1 / 60)


def open_controls(ctx: GameContext) -> tuple[SceneManager, ControlsScene]:
    scenes = SceneManager()
    scene = ControlsScene(ctx)
    scenes.push(scene)
    scenes.update(1 / 60)
    return scenes, scene


def inner(scene: ControlsScene) -> ScrollList:
    found = scene.ui.root.children[1]
    assert isinstance(found, ScrollList)
    return found


def rebind_row(scenes: SceneManager, scene: ControlsScene, label: str, key: int) -> None:
    for _ in range(40):
        current = inner(scene).current
        if isinstance(current, KeybindField) and current.text == label:
            press(scenes, pygame.K_RETURN)
            press(scenes, key)
            return
        press(scenes, pygame.K_DOWN)
    msg = f"no row {label}"
    raise AssertionError(msg)


def test_rebinding_updates_the_settings(ctx: GameContext) -> None:
    scenes, scene = open_controls(ctx)
    rebind_row(scenes, scene, "Jump", pygame.K_q)
    assert ctx.settings.controls.keys[Action.JUMP][0] == "q"


def test_a_conflict_moves_the_key_and_says_so(ctx: GameContext) -> None:
    scenes, scene = open_controls(ctx)
    rebind_row(scenes, scene, "Dash", pygame.K_SPACE)
    controls = ctx.settings.controls.keys
    assert controls[Action.DASH][0] == "space"
    assert "space" not in controls[Action.JUMP]
    assert "Jump" in scene.notice.text


def test_reset_restores_defaults(ctx: GameContext) -> None:
    scenes, scene = open_controls(ctx)
    rebind_row(scenes, scene, "Jump", pygame.K_q)
    for _ in range(40):
        current = inner(scene).current
        if current is not None and current.text == "Reset to defaults":
            press(scenes, pygame.K_RETURN)
            break
        press(scenes, pygame.K_DOWN)
    assert ctx.settings.controls.keys == default_bindings().keys


def test_closing_saves_and_gameplay_picks_up_the_new_keys(ctx: GameContext) -> None:
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.update(1 / 60)
    scenes.push(SettingsScene(ctx))
    scenes.update(1 / 60)
    scenes.push(ControlsScene(ctx))
    scenes.update(1 / 60)
    assert isinstance(scenes.top, ControlsScene)
    rebind_row(scenes, scenes.top, "Jump", pygame.K_q)
    press(scenes, pygame.K_ESCAPE)
    press(scenes, pygame.K_ESCAPE)
    assert scenes.top is game
    saved = json.loads(ctx.storage.read(SETTINGS_KEY) or "")
    assert saved["data"]["controls"]["keys"]["jump"][0] == "q"
    game.mapper.handle(pygame.Event(pygame.KEYDOWN, key=pygame.K_q))
    assert Action.JUMP in game.mapper.sample()
