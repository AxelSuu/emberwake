"""Runs the player controller on every entity with a `Body` and a `Motor`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, TileSource
from emberwake.game.combat import Knockback
from emberwake.game.grants import Loadout
from emberwake.game.player.controller import Motor, step
from emberwake.game.player.tuning import PlayerTuning

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


def player_system(world: World, dt: float) -> None:
    actions = world.resource(InputState)
    grid = world.resource(TileSource)
    tuning = world.resource(PlayerTuning)
    bus = world.resource(EventBus)
    can_dash = not world.has_resource(Loadout) or world.resource(Loadout).has("dash")
    for eid, body, motor in list(world.query(Body, Motor)):
        if world.has(eid, Knockback):
            push = world.get(eid, Knockback)
            motor.vx, motor.vy = push.vx, push.vy
            world.remove(eid, Knockback)
        if not motor.dead:
            for event in step(body, motor, actions, grid, tuning, dt, can_dash=can_dash):
                bus.publish(event)
