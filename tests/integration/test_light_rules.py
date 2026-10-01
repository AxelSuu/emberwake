"""In a real room the ember drains in the dark, and running out costs a life."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.scene import SceneManager
from emberwake.game.light import Ember
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Test_Room")
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def test_the_ember_drains_in_a_dark_room(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    full = game.world.get(game.player, Ember).current
    for _ in range(120):
        scenes.update(STEP)
    assert game.world.get(game.player, Ember).current < full


def test_running_out_of_ember_respawns_with_a_full_one(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.world.get(game.player, Ember).current = 0.01
    for _ in range(10):
        scenes.update(STEP)
    assert game.respawn_in > 0 or game.motor.dead
    for _ in range(60):
        scenes.update(STEP)
    ember = game.world.get(game.player, Ember)
    assert ember.current > 90
    assert not game.motor.dead
