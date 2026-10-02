"""Dev tools: warping to a room and toggling flags in a running game."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import SceneManager
from emberwake.game.scenes.dev import FlagsScene, WarpScene
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def press(scenes: SceneManager, key: int) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    scenes.update(STEP)


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def test_warp_moves_the_player_into_the_room_and_streams_it(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.warp("Enemy_Yard")
    for _ in range(3):
        scenes.update(STEP)
    assert game.room == "Enemy_Yard"
    assert game.rooms.graph.rects["Enemy_Yard"].collidepoint(game.body.center_x, game.body.y)
    assert game.progress.data.discovered[-1] == game.rooms.graph.levels["Enemy_Yard"].iid


def test_f6_lists_rooms_and_picking_one_warps(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    press(scenes, pygame.K_F6)
    warp = scenes.top
    assert isinstance(warp, WarpScene)
    while (current := warp.list.current) is not None and current.text != "Upper_Room":
        press(scenes, pygame.K_UP)
    press(scenes, pygame.K_RETURN)
    scenes.update(STEP)
    assert scenes.top is game
    assert game.room == "Upper_Room"


def test_f7_toggles_flags_in_the_save(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    press(scenes, pygame.K_F7)
    flags = scenes.top
    assert isinstance(flags, FlagsScene)
    assert {"met_tinker", "up_hp"} <= {row.text for row in flags.list.children}
    while (current := flags.list.current) is not None and current.text != "met_tinker":
        press(scenes, pygame.K_DOWN)
    press(scenes, pygame.K_RETURN)
    assert game.progress.data.flags["met_tinker"] == 1
    press(scenes, pygame.K_RETURN)
    assert "met_tinker" not in game.progress.data.flags


def test_flags_from_the_command_line_seed_the_game(ctx: GameContext) -> None:
    ctx.flags = {"up_hp": 2}
    _, game = start(ctx)
    assert game.progress.data.flags["up_hp"] == 2
