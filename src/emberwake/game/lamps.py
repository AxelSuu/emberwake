"""Lamp posts: lit by the swing, held by a lit beacon, put out by light-eaters.

A lamp is a `Lamp`, a `Strikeable` and, while lit, a `LightSource`; an unlit one gives no light
at all. `Lamp` is persisted by iid, so the lamps you lit stay lit. See docs/specs/lamps.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game.beacons import Beacon
from emberwake.game.light import LightSource
from emberwake.game.player.swing import Strikeable

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId, World


@dataclass(frozen=True, slots=True)
class LampTuning:
    """What a lit lamp looks like (content/feel.toml, ``[lamps]``)."""

    radius: float = 80.0
    strength: float = 1.0
    color: str = "#fbb954"


@component
@dataclass(slots=True)
class Lamp:
    lit: bool = False
    protected: bool = False
    """Lit for good: light-eaters cannot snuff it."""


@component
@dataclass(slots=True)
class Shelter:
    """The beacon (an iid, in any room) whose light holds this lamp; empty for none."""

    beacon: str = ""


@dataclass(frozen=True, slots=True)
class LampLit:
    iid: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class LampSnuffed:
    iid: str
    x: float
    y: float


def lamp_system(world: World, dt: float) -> None:
    """Light struck lamps, protect lit ones under a lit beacon, and give lit ones their light."""
    tuning, bus = world.resource(LampTuning), world.resource(EventBus)
    for eid, body, lamp, strikeable in list(world.query(Body, Lamp, Strikeable)):
        if strikeable.struck is not None and not lamp.lit:
            lamp.lit = True
            iid = world.get(eid, Identity).iid
            bus.publish(LampLit(iid, body.center_x, body.y + body.height / 2))
        if lamp.lit and not lamp.protected:
            shelter = world.find(eid, Shelter)
            lamp.protected = shelter is not None and _beacon_lit(world, shelter.beacon)
        if lamp.lit != world.has(eid, LightSource):
            if lamp.lit:
                light = LightSource(tuning.radius, tuning.strength, tuning.color)
                world.add(eid, light)
            else:
                world.remove(eid, LightSource)


def _beacon_lit(world: World, iid: str) -> bool:
    """Whether the beacon `iid` is lit, loaded or not."""
    if not iid:
        return False
    spawner = world.resource(Spawner)
    eid = spawner.resolve(iid)
    if eid is not None:
        beacon = world.find(eid, Beacon)
        return beacon is not None and beacon.lit
    return bool(spawner.state.entities.get(iid, {}).get("Beacon", {}).get("lit", False))


def snuff(world: World, eid: EntityId) -> bool:
    """Put out lamp `eid` if it is lit and unprotected; returns whether it went out."""
    lamp = world.find(eid, Lamp)
    if lamp is None or not lamp.lit or lamp.protected:
        return False
    lamp.lit = False
    body, identity = world.get(eid, Body), world.get(eid, Identity)
    world.resource(EventBus).publish(
        LampSnuffed(identity.iid, body.center_x, body.y + body.height / 2)
    )
    return True


def nearest_prey(world: World, x: float, y: float, radius: float) -> EntityId | None:
    """The nearest lit, unprotected lamp within `radius` px of the point, if any."""
    best: tuple[float, EntityId] | None = None
    for eid, body, lamp in world.query(Body, Lamp):
        if not lamp.lit or lamp.protected:
            continue
        distance = math.hypot(x - body.center_x, y - (body.y + body.height / 2))
        if distance <= radius and (best is None or (distance, eid) < best):
            best = (distance, eid)
    return best[1] if best else None
