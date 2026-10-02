"""What the lantern breaks for good, the embers that fly out, and platforms that crumble underfoot.

Rules: docs/specs/breakables.md. `breakable_system` reads `Strikeable.struck`, so it runs after
`strike_system`. Broken things are retired by iid, so they never spawn again.
"""

from __future__ import annotations

import math
import random
import zlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body, Tile, TileSource, move
from emberwake.engine.world.rooms import WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game.components import Sprite
from emberwake.game.interact import Collected, overlap, player_body
from emberwake.game.player.controller import Motor
from emberwake.game.player.swing import Strikeable

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

EMBER = 10
"""Size of a loose ember, px."""
SCATTER = (-150.0, -30.0)
"""Degrees a loose ember is flung at: upward, either side."""
BOUNCE = 0.4
"""Share of a loose ember's speed kept when it hits a tile."""
EPSILON = 1e-6


@dataclass(frozen=True, slots=True)
class BreakTuning:
    """Breakables, their embers and crumbling platforms (content/feel.toml, ``[breakables]``).

    Seconds, px/s and px/s²; `hitstop` in ticks.
    """

    crumble_delay: float = 0.5
    """From the player landing until a crumbling platform clears."""
    crumble_return: float = 2.0
    """How long a crumbling platform stays gone, at least."""
    ember_speed: tuple[float, float] = (60.0, 140.0)
    ember_gravity: float = 600.0
    ember_settle: float = 0.4
    """Seconds before loose embers home in on the player."""
    ember_pull: float = 240.0
    hitstop: int = 3
    trauma: float = 0.15


@component
@dataclass(slots=True)
class Breakable:
    """Breaks for good when struck, flinging `embers`."""

    blocks: bool = False
    """Fills its cells with solid tiles until broken (cracked walls, crates)."""
    embers: int = 0


@component
@dataclass(slots=True)
class LooseEmber:
    """An ember flung out of something broken; the player collects it on touch."""

    vx: float = 0.0
    vy: float = 0.0
    source: str = ""
    """Iid of what it came out of."""
    age: float = 0.0


@component
@dataclass(slots=True)
class Crumble:
    """A one-way platform that gives way under the player and comes back."""

    state: Literal["whole", "shaking", "gone"] = "whole"
    timer: float = 0.0
    """Seconds in `state`."""


@dataclass(frozen=True, slots=True)
class Broken:
    """Something broke for good: its rect, for debris and sound."""

    iid: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class Crumbled:
    """A crumbling platform gave way: its rect."""

    x: float
    y: float
    width: float
    height: float


def fill(grid: WorldGrid, body: Body, tile: Tile) -> None:
    """Set every cell under `body` to `tile`."""
    size = grid.tile_size
    for row in range(math.floor(body.y / size), math.ceil(body.bottom / size)):
        for column in range(math.floor(body.x / size), math.ceil((body.x + body.width) / size)):
            grid.set(column, row, tile)


def fling(world: World, iid: str, body: Body, count: int, tuning: BreakTuning) -> None:
    """Spawn `count` loose embers bursting out of `body`, scattered the same way every time."""
    rng = random.Random(zlib.crc32(iid.encode()))
    x, y = body.center_x - EMBER / 2, body.y + body.height / 2 - EMBER / 2
    for _ in range(count):
        angle = math.radians(rng.uniform(*SCATTER))
        speed = rng.uniform(*tuning.ember_speed)
        motion = LooseEmber(math.cos(angle) * speed, math.sin(angle) * speed, iid)
        world.spawn(Body(x, y, EMBER, EMBER), Sprite("ember"), motion)


def breakable_system(world: World, dt: float) -> None:
    """Blocking breakables fill their cells; a struck one breaks for good and flings embers."""
    grid, spawner = world.resource(WorldGrid), world.resource(Spawner)
    bus, tuning = world.resource(EventBus), world.resource(BreakTuning)
    for eid, body, breakable, strikeable in list(world.query(Body, Breakable, Strikeable)):
        broken = strikeable.struck is not None
        if breakable.blocks:
            fill(grid, body, Tile.EMPTY if broken else Tile.SOLID)
        if not broken:
            continue
        iid = world.get(eid, Identity).iid
        fling(world, iid, body, breakable.embers, tuning)
        bus.publish(Broken(iid, body.x, body.y, body.width, body.height))
        spawner.retire(eid)


def loose_ember_system(world: World, dt: float) -> None:
    """Loose embers fall and bounce, then fly to the player, who collects them on touch."""
    tuning, grid = world.resource(BreakTuning), world.resource(TileSource)
    bus, player = world.resource(EventBus), player_body(world)
    for eid, body, ember in list(world.query(Body, LooseEmber)):
        ember.age += dt
        if player is not None and overlap(body, player):
            bus.publish(Collected(ember.source, 1))
            world.despawn(eid)
        elif player is not None and ember.age + EPSILON >= tuning.ember_settle:
            _home(body, player, tuning.ember_pull * dt)
        else:
            ember.vy += tuning.ember_gravity * dt
            contacts = move(grid, body, ember.vx * dt, ember.vy * dt)
            if contacts.ground or contacts.ceiling:
                ember.vx, ember.vy = ember.vx * BOUNCE, -ember.vy * BOUNCE
            if contacts.left or contacts.right:
                ember.vx = -ember.vx * BOUNCE


def _home(body: Body, player: Body, reach: float) -> None:
    dx = player.center_x - body.center_x
    dy = player.y + player.height / 2 - (body.y + body.height / 2)
    distance = math.hypot(dx, dy)
    if distance > 0:
        step = min(distance, reach) / distance
        body.x += dx * step
        body.y += dy * step


def crumble_system(world: World, dt: float) -> None:
    """Crumbling platforms shake under the player, give way, and come back once clear of it."""
    tuning, grid = world.resource(BreakTuning), world.resource(WorldGrid)
    bus, player = world.resource(EventBus), player_body(world)
    standing = [body for _, body, motor in world.query(Body, Motor) if motor.grounded]
    for _, body, crumble in world.query(Body, Crumble):
        crumble.timer += dt
        if crumble.state == "whole" and any(_on_top(feet, body) for feet in standing):
            crumble.state, crumble.timer = "shaking", 0.0
        elif crumble.state == "shaking" and crumble.timer + EPSILON >= tuning.crumble_delay:
            crumble.state, crumble.timer = "gone", 0.0
            bus.publish(Crumbled(body.x, body.y, body.width, body.height))
        elif (
            crumble.state == "gone"
            and crumble.timer + EPSILON >= tuning.crumble_return
            and (player is None or not overlap(body, player))
        ):
            crumble.state, crumble.timer = "whole", 0.0
        fill(grid, body, Tile.EMPTY if crumble.state == "gone" else Tile.ONE_WAY)


def _on_top(feet: Body, platform: Body) -> bool:
    return (
        abs(feet.bottom - platform.y) < 0.5
        and feet.x < platform.x + platform.width
        and platform.x < feet.x + feet.width
    )
