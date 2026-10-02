"""How to play lists the controls with their current keys and tips that name them."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import SceneManager
from emberwake.engine.ui import Row
from emberwake.game.actions import Action
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.how_to_play import HowToPlayScene, key_name
from emberwake.game.scenes.menu import MenuScene
from emberwake.game.scenes.pause import PauseScene
from emberwake.game.scenes.title import TitleScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


def press(scenes: SceneManager, key: int) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    scenes.update(1 / 60)


def texts(scene: HowToPlayScene) -> dict[str, str]:
    return {row.text: row.value for row in scene.rows if isinstance(row, Row)}


def test_every_action_is_listed_with_its_keys(ctx: GameContext) -> None:
    rows = texts(HowToPlayScene(ctx))
    assert rows["Jump"] == "Space / Z"
    assert rows["Swing lantern"] == "C / J"
    assert rows["Dash"] == "X / Left Shift / K"
    assert len([row for row in rows if row in {"Left", "Right", "Up", "Down"}]) == 4
    assert all(value for value in rows.values() if value)


def test_tips_name_the_keys_as_bound_now(ctx: GameContext) -> None:
    ctx.settings.controls.keys[Action.JUMP] = ["q"]
    rows = HowToPlayScene(ctx).rows
    wall = next(row.text for row in rows if row.text.startswith("Slide down a wall"))
    assert "press Q" in wall
    assert "{" not in "".join(row.text for row in rows)


def test_key_names_read_like_keys() -> None:
    names = key_name("left shift"), key_name("e"), key_name("space")
    assert names == ("Left Shift", "E", "Space")


def test_reached_from_the_main_menu_and_back(ctx: GameContext) -> None:
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    scenes.update(1 / 60)
    press(scenes, pygame.K_SPACE)
    menu = scenes.top
    assert isinstance(menu, MenuScene)
    while (current := menu.ui.root.current) is not None and current.text != "How to play":
        press(scenes, pygame.K_DOWN)
    press(scenes, pygame.K_RETURN)
    assert isinstance(scenes.top, HowToPlayScene)
    press(scenes, pygame.K_ESCAPE)
    assert scenes.top is menu


def test_reached_from_the_pause_menu(ctx: GameContext) -> None:
    scenes = SceneManager()
    scenes.push(GameplayScene(ctx))
    scenes.update(1 / 60)
    press(scenes, pygame.K_ESCAPE)
    press(scenes, pygame.K_DOWN)
    press(scenes, pygame.K_DOWN)
    press(scenes, pygame.K_RETURN)
    assert isinstance(scenes.top, HowToPlayScene)
    press(scenes, pygame.K_ESCAPE)
    assert isinstance(scenes.top, PauseScene)
