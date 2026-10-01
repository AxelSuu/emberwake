"""Light as a resource and a rule: the player's ember drains in the dark, lightforms need light.

Light sources are lit beacons, anything with a `LightSource` (flares, braziers) and the
player's own lantern. Light falls off linearly to nothing at a source's radius. The ember refills
only in *other* light, so carrying the lantern through a dark room still drains it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body, Tile
from emberwake.engine.world.rooms import WorldGrid
from emberwake.game.beacons import Beacon
from emberwake.game.interact import player_body
from emberwake.game.player.controller import Died, Motor

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


@dataclass(frozen=True, slots=True)
class LightTuning:
    """Numbers for the light rules, in px and per second (content/feel.toml, ``[light]``)."""

    ember_max: float = 100.0
    drain: float = 2.0
    """Ember lost per second in darkness."""
    refill: float = 25.0
    """Ember gained per second in light."""
    lit_threshold: float = 0.05
    """Light level (0 to 1) at which something counts as lit."""
    lantern_radius: float = 56.0
    beacon_radius: float = 96.0


@component
@dataclass(slots=True)
class Ember:
    """The player's light: HP-like, drained by darkness, refilled by light."""

    current: float = 100.0
    in_light: bool = True
    max: float = 100.0
    """The most it can hold; shop upgrades raise it."""


@component
@dataclass(slots=True)
class LightSource:
    """Something that lights its surroundings (a flare, a brazier)."""

    radius: float = 64.0
    strength: float = 1.0
    color: str = ""
    """Hex color of the light; empty is the lantern's warm amber."""


@component
@dataclass(slots=True)
class Lightform:
    """A platform that exists only while it is lit."""

    solid: bool = False
    """Whether it is currently solid (and its sprite drawn active)."""


def falloff(distance: float, radius: float, strength: float = 1.0) -> float:
    """Light from a source `distance` px away: `strength` at its centre, 0 at `radius`."""
    if radius <= 0 or distance >= radius:
        return 0.0
    return strength * (1.0 - distance / radius)


def light_at(world: World, x: float, y: float, *, lantern: bool = True) -> float:
    """The brightest light (0 to 1) reaching the point, with or without the player's lantern."""
    tuning = world.resource(LightTuning)
    best = 0.0
    for _, body, beacon in world.query(Body, Beacon):
        if beacon.lit:
            d = math.hypot(x - body.center_x, y - (body.y + body.height / 2))
            best = max(best, falloff(d, tuning.beacon_radius))
    for _, body, source in world.query(Body, LightSource):
        d = math.hypot(x - body.center_x, y - (body.y + body.height / 2))
        best = max(best, falloff(d, source.radius, source.strength))
    if lantern and (player := player_body(world)) is not None:
        d = math.hypot(x - player.center_x, y - (player.y + player.height / 2))
        best = max(best, falloff(d, tuning.lantern_radius))
    return min(best, 1.0)


def ember_system(world: World, dt: float) -> None:
    """Drain the ember in darkness, refill it in light, and kill the player at zero."""
    tuning, bus = world.resource(LightTuning), world.resource(EventBus)
    for _, body, motor, ember in world.query(Body, Motor, Ember):
        if motor.dead:
            continue
        centre_y = body.y + body.height / 2
        ember.in_light = light_at(world, body.center_x, centre_y, lantern=False) > 0
        rate = tuning.refill if ember.in_light else -tuning.drain
        ember.current = min(max(ember.current + rate * dt, 0.0), ember.max)
        if ember.current <= 0:
            motor.dead = True
            bus.publish(Died(body.center_x, body.bottom))


def lightform_system(world: World, dt: float) -> None:
    """Lightforms become one-way platforms while lit and vanish when the light goes."""
    tuning, grid = world.resource(LightTuning), world.resource(WorldGrid)
    size = grid.tile_size
    for _, body, form in world.query(Body, Lightform):
        lit = light_at(world, body.center_x, body.y + body.height / 2) >= tuning.lit_threshold
        if lit == form.solid:
            continue
        form.solid = lit
        tile = Tile.ONE_WAY if lit else Tile.EMPTY
        for row in range(math.floor(body.y / size), math.ceil((body.y + body.height) / size)):
            for column in range(math.floor(body.x / size), math.ceil((body.x + body.width) / size)):
                grid.set(column, row, tile)
