"""The Cinder: the embers a player drops on dying, picked up again by touching them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.components import Sprite
from emberwake.game.interact import Trigger

if TYPE_CHECKING:
    from emberwake.engine.ecs import World
    from emberwake.game.data.save import Cinder

IID = "cinder"
SIZE = 12


@component
@dataclass(slots=True)
class CinderMark:
    embers: int = 0
    taken: bool = False


@dataclass(frozen=True, slots=True)
class CinderRecovered:
    embers: int
    x: float
    y: float


def cinder_parts(cinder: Cinder) -> tuple[object, ...]:
    """The components of the Cinder entity, lying where `cinder` says."""
    body = Body(cinder.x - SIZE / 2, cinder.y - SIZE, SIZE, SIZE)
    identity = Identity(IID, cinder.room, IID)
    return identity, body, Sprite(image="cinder"), Trigger(), CinderMark(cinder.embers)


def cinder_system(world: World, dt: float) -> None:
    """Touching the Cinder takes its embers back."""
    for eid, trigger, mark in world.query(Trigger, CinderMark):
        if trigger.inside and not mark.taken:
            mark.taken = True
            body = world.get(eid, Body)
            bus = world.resource(EventBus)
            bus.publish(CinderRecovered(mark.embers, body.center_x, body.y + body.height / 2))
            world.despawn(eid)
