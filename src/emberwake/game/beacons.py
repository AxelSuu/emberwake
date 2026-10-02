"""Beacons: relight one to save, refill the dash and set where the game continues."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.combat import Health
from emberwake.game.flags import Facts
from emberwake.game.interact import Interactable
from emberwake.game.player.controller import Motor
from emberwake.game.player.tuning import PlayerTuning

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


@component
@dataclass(slots=True)
class Beacon:
    lit: bool = False


@component
@dataclass(slots=True)
class BeaconFlag:
    """A save flag set to 1 when the beacon is lit, so a FlagSwitch can wire it to doors.

    Apart from `Beacon` so saves never carry it: it always comes from the level.
    """

    flag: str = ""


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

    Its `BeaconFlag`, if any, is set. It asks for a save via `BeaconLit`; others refill flares and
    reset enemies on `Rested`.
    """
    for eid, interactable, beacon in world.query(Interactable, Beacon):
        if not interactable.used:
            continue
        beacon.lit = True
        if (raises := world.find(eid, BeaconFlag)) and raises.flag:
            world.resource(Facts).flags[raises.flag] = 1
        charges = world.resource(PlayerTuning).dash_charges
        for _, motor in world.query(Motor):
            motor.dash_charges = max(motor.dash_charges, charges)
        for _, _motor, health in world.query(Motor, Health):
            health.current = health.max
        world.resource(EventBus).publish(Rested())
        identity, body = world.get(eid, Identity), world.get(eid, Body)
        lit = BeaconLit(identity.iid, identity.room, body.center_x, body.bottom)
        world.resource(EventBus).publish(lit)
