"""Beacons: relight one to save, refill the dash and set where the game continues."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.combat import Health
from emberwake.game.interact import Interactable
from emberwake.game.player.controller import Motor
from emberwake.game.player.tuning import PlayerTuning

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


@component
@dataclass(slots=True)
class Beacon:
    lit: bool = False


@dataclass(frozen=True, slots=True)
class BeaconLit:
    iid: str
    room: str
    x: float
    y: float
    """The beacon's feet in world px, where the game continues."""


@dataclass(frozen=True, slots=True)
class Rested:
    """The player rested at a beacon: healed, refilled, and the room's enemies come back."""


def beacon_system(world: World, dt: float) -> None:
    """A used beacon lights (again) and is a rest: dash, health and flame refilled.

    It asks for a save via `BeaconLit`; others refill flares and reset enemies on `Rested`.
    """
    for eid, interactable, beacon in world.query(Interactable, Beacon):
        if not interactable.used:
            continue
        beacon.lit = True
        charges = world.resource(PlayerTuning).dash_charges
        for _, motor in world.query(Motor):
            motor.dash_charges = max(motor.dash_charges, charges)
        for _, _motor, health in world.query(Motor, Health):
            health.current = health.max
        world.resource(EventBus).publish(Rested())
        identity, body = world.get(eid, Identity), world.get(eid, Body)
        lit = BeaconLit(identity.iid, identity.room, body.center_x, body.bottom)
        world.resource(EventBus).publish(lit)
