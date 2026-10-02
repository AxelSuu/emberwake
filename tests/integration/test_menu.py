"""The main menu: continue, new game, load with slot select, settings and quit."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import SceneManager
from emberwake.game.data.save import SaveSlot, save_slot
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.menu import MenuScene, SlotScene
from emberwake.game.scenes.settings import SettingsScene
from emberwake.game.scenes.title import TitleScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


def press(scenes: SceneManager, key: int) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    scenes.update(1 / 60)


def menu(ctx: GameContext) -> SceneManager:
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    scenes.update(1 / 60)
    press(scenes, pygame.K_SPACE)
    assert isinstance(scenes.top, MenuScene)
    return scenes


def pick(scenes: SceneManager, text: str) -> None:
    """Focus the row starting with `text` and accept it."""
    scene = scenes.top
    assert isinstance(scene, MenuScene | SlotScene)
    for _ in range(8):
        current = scene.ui.root.current
        if current is not None and current.text.startswith(text):
            press(scenes, pygame.K_RETURN)
            return
        press(scenes, pygame.K_DOWN)
    msg = f"no focusable row starts with {text!r}"
    raise AssertionError(msg)


def test_continue_is_disabled_without_saves(ctx: GameContext) -> None:
    scenes = menu(ctx)
    assert isinstance(scenes.top, MenuScene)
    assert not scenes.top.ui.root.children[0].enabled
    assert scenes.top.ui.root.current is scenes.top.ui.root.children[1]


def test_continue_resumes_the_most_played_slot(ctx: GameContext) -> None:
    ctx.slot = 1
    save_slot(ctx.storage, 2, SaveSlot(room="Lab_Lever_Hall", playtime=50))
    save_slot(ctx.storage, 3, SaveSlot(room="Lab_Lever_Hall", playtime=90))
    scenes = menu(ctx)
    pick(scenes, "Continue")
    assert isinstance(scenes.top, GameplayScene)
    assert ctx.slot == 3
    assert len(scenes.scenes) == 1


def test_load_offers_only_saved_slots(ctx: GameContext) -> None:
    save_slot(ctx.storage, 2, SaveSlot(room="Lab_Lever_Hall"))
    scenes = menu(ctx)
    pick(scenes, "Load")
    assert isinstance(scenes.top, SlotScene)
    assert [b.enabled for b in scenes.top.buttons.values()] == [False, True, False]
    pick(scenes, "Slot 2")
    assert isinstance(scenes.top, GameplayScene)
    assert ctx.slot == 2
    assert not ctx.new_game


def test_new_game_on_an_empty_slot_starts_at_once(ctx: GameContext) -> None:
    scenes = menu(ctx)
    pick(scenes, "New game")
    pick(scenes, "Slot 2")
    assert isinstance(scenes.top, GameplayScene)
    assert ctx.slot == 2


def test_new_game_on_an_occupied_slot_needs_confirmation(ctx: GameContext) -> None:
    save_slot(ctx.storage, 1, SaveSlot(room="Lab_Lever_Hall"))
    scenes = menu(ctx)
    pick(scenes, "New game")
    pick(scenes, "Slot 1")
    assert isinstance(scenes.top, SlotScene)
    pick(scenes, "Overwrite slot 1")
    assert isinstance(scenes.top, GameplayScene)
    assert scenes.top.progress.data.room != "Lab_Lever_Hall"


def test_back_unwinds_to_the_title(ctx: GameContext) -> None:
    scenes = menu(ctx)
    pick(scenes, "Settings")
    assert isinstance(scenes.top, SettingsScene)
    press(scenes, pygame.K_ESCAPE)
    assert isinstance(scenes.top, MenuScene)
    press(scenes, pygame.K_ESCAPE)
    assert isinstance(scenes.top, TitleScene)


def test_quit_closes_everything(ctx: GameContext) -> None:
    scenes = menu(ctx)
    pick(scenes, "Quit")
    assert not scenes
