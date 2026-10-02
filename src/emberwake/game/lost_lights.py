"""Lost Lights: small spirits that follow the player to a beacon, and are rescued there.

A light notices the player nearby and floats `delay` seconds behind them, along a trail of their
past positions. Coming near a beacon rescues it for good: the flag ``lost_light_<id>`` is set and
``lost_lights`` counts it. When the player dies it floats back to where it was placed.
See ``docs/specs/lore-and-lost-lights.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.engine.world.rooms import RoomStreamer
from emberwake.engine.world.spawning import Identity
from emberwake.game.beacons import Beacon
from emberwake.game.components import Sprite
from emberwake.game.flags import Facts
from emberwake.game.interact import overlap, player_body
from emberwake.game.light import LightSource

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

SMOOTHING = 20.0
"""How fast (per second) a light closes in on its place in the trail."""


@component
@dataclass(slots=True)
class LostLight:
    """Saved by iid; `rescued` counts toward light %."""

    rescued: bool = False


@component
@dataclass(slots=True)
class Spirit:
    """How a Lost Light behaves and where it is now."""

    id: str = ""
    delay: float = 0.5
    """Seconds behind the player."""
    notice: float = 32.0
    """Distance from the player (px) at which it starts to follow."""
    rescue: float = 24.0
    """Distance from a beacon (px) at which it is rescued."""
    following: bool = False
    placed: bool = False
    """`home` and `home_room` are known."""
    home: tuple[float, float] = (0.0, 0.0)
    """Top left of its body where it was placed."""
    home_room: str = ""
    trail: list[tuple[float, float]] = field(default_factory=list)
    """Where the player was, newest last: centre points, `delay` seconds' worth."""


@dataclass(frozen=True, slots=True)
class LostLightRescued:
    id: str
    x: float
    y: float


def lost_light_system(world: World, dt: float) -> None:
    """Notice, follow, rescue and send home the Lost Lights."""
    player = player_body(world)
    active = world.resource(RoomStreamer).active
    for eid, body, light, spirit, identity in list(world.query(Body, LostLight, Spirit, Identity)):
        if light.rescued:
            if world.has(eid, Sprite):
                world.remove(eid, Sprite, LightSource)
            continue
        if not spirit.placed:
            spirit.home, spirit.home_room, spirit.placed = (body.x, body.y), identity.room, True
        if player is None:
            _send_home(spirit, body, identity)
        elif spirit.following or _near(body, player, spirit.notice):
            spirit.following = True
            _follow(spirit, body, player, dt)
            identity.room = active or identity.room
            _rescue(world, light, spirit, body, identity)


def _near(body: Body, player: Body, distance: float) -> bool:
    return math.hypot(body.center_x - player.center_x, _mid(body) - _mid(player)) <= distance


def _mid(body: Body) -> float:
    return body.y + body.height / 2


def _follow(spirit: Spirit, body: Body, player: Body, dt: float) -> None:
    spirit.trail.append((player.center_x, _mid(player)))
    del spirit.trail[: -max(1, round(spirit.delay / dt))]
    x, y = spirit.trail[0]
    ease = 1 - math.exp(-SMOOTHING * dt)
    body.x += (x - body.width / 2 - body.x) * ease
    body.y += (y - body.height / 2 - body.y) * ease


def _send_home(spirit: Spirit, body: Body, identity: Identity) -> None:
    if spirit.following:
        spirit.following = False
        spirit.trail.clear()
        body.x, body.y = spirit.home
        identity.room = spirit.home_room


def _rescue(world: World, light: LostLight, spirit: Spirit, body: Body, identity: Identity) -> None:
    if not any(overlap(body, beacon, spirit.rescue) for _, beacon, _ in world.query(Body, Beacon)):
        return
    light.rescued, spirit.following = True, False
    identity.room = spirit.home_room
    flags = world.resource(Facts).flags
    flags[f"lost_light_{spirit.id}"] = 1
    flags["lost_lights"] = flags.get("lost_lights", 0) + 1
    event = LostLightRescued(spirit.id, body.center_x, _mid(body))
    world.resource(EventBus).publish(event)
