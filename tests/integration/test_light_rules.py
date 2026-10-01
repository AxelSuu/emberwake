"""In a real room the flame drains in the dark, and running out costs health slowly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.scene import SceneManager
from emberwake.game.combat import Health
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


def test_running_out_of_flame_costs_health_but_does_not_kill_at_once(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    health = game.world.get(game.player, Health)
    full = health.current
    game.world.get(game.player, Ember).current = 0.01
    for _ in range(60):
        scenes.update(STEP)
    assert not game.motor.dead
    assert health.current == full
    for _ in range(round(game.feel.light.gutter_every * 60)):
        scenes.update(STEP)
    assert health.current == full - 1
