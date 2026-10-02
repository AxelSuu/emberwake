"""The map screen, opened from play and from the pause menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from tests.integration.test_how_to_play import press

from emberwake.engine.scene import SceneManager
from emberwake.game.map import Icon
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.map import MapScene
from emberwake.game.scenes.pause import PauseScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


def playing(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.update(1 / 60)
    return scenes, game


def test_m_opens_the_map_of_the_rooms_entered_and_closes_it(ctx: GameContext) -> None:
    scenes, game = playing(ctx)
    press(scenes, pygame.K_m)
    top = scenes.top
    assert isinstance(top, MapScene)
    assert [room.visited for room in top.view.rooms] == [True]
    assert Icon.PLAYER in [icon.kind for icon in top.view.icons]
    canvas = pygame.Surface(ctx.canvas_size)
    for _ in range(40):
        scenes.update(1 / 60)
        scenes.draw(canvas, 1.0)
    press(scenes, pygame.K_m)
    assert scenes.top is game


def test_the_pause_menu_opens_the_map_and_back_returns_to_it(ctx: GameContext) -> None:
    scenes, _ = playing(ctx)
    press(scenes, pygame.K_ESCAPE)
    press(scenes, pygame.K_DOWN)
    press(scenes, pygame.K_RETURN)
    assert isinstance(scenes.top, MapScene)
    press(scenes, pygame.K_ESCAPE)
    assert isinstance(scenes.top, PauseScene)


def test_a_bought_map_outlines_every_room_of_the_area(ctx: GameContext) -> None:
    scenes, game = playing(ctx)
    game.progress.data.inventory["map.quarter"] = 1
    press(scenes, pygame.K_m)
    top = scenes.top
    assert isinstance(top, MapScene)
    quarter = [
        level
        for level in game.rooms.graph.levels.values()
        if (level.field("Area") or "quarter") == "quarter"
    ]
    assert len(top.view.rooms) == len(quarter)
    assert sum(room.visited for room in top.view.rooms) == 1
