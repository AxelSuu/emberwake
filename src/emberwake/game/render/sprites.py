"""Sprite state from gameplay state, decided once per tick before drawing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.game.beacons import Beacon
from emberwake.game.components import Sprite
from emberwake.game.enemies import Brain
from emberwake.game.interact import Switch
from emberwake.game.lamps import Lamp
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId, World


def sprite_system(world: World, dt: float) -> None:
    """Switches, doors, beacons and lamps show active; enemies show what their brain is doing."""
    for eid, sprite in world.query(Sprite):
        sprite.active = _active(world, eid)
        brain = world.find(eid, Brain)
        state = brain.state if brain is not None else ""
        sprite.since = 0.0 if state != sprite.state else sprite.since + dt
        sprite.state = state


def _active(world: World, eid: EntityId) -> bool:
    switch = world.find(eid, Switch)
    if switch is not None and switch.on:
        return True
    door = world.find(eid, Door)
    if door is not None and door.open:
        return True
    beacon = world.find(eid, Beacon)
    if beacon is not None:
        return beacon.lit
    lamp = world.find(eid, Lamp)
    return lamp is not None and lamp.lit
