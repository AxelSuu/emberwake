"""Runs the player controller on every entity with a `Body` and a `Motor`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, TileGrid
from emberwake.game.player.controller import Motor, step
from emberwake.game.player.tuning import PlayerTuning

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


def player_system(world: World, dt: float) -> None:
    actions = world.resource(InputState)
    grid = world.resource(TileGrid)
    tuning = world.resource(PlayerTuning)
    bus = world.resource(EventBus)
    for _, body, motor in world.query(Body, Motor):
        if not motor.dead:
            for event in step(body, motor, actions, grid, tuning, dt):
                bus.publish(event)
