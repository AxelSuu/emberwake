"""Lifts and moving platforms: boxes on a path that carry what stands on them.

Rules: docs/specs/lifts.md. A platform is moved a sub-pixel step per tick and solid for the
player and crates through the engine's box mover. `platform_system` runs before the player, so a
rider is carried by the platform's displacement before its own move. Where a platform is on its
path is saved by iid (`PlatformRest`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING

from emberwake.engine.ecs import component
from emberwake.engine.physics import Body, TileSource, move, overlaps
from emberwake.engine.physics.kinematic import EPSILON
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game.player.controller import Motor
from emberwake.game.signals import Receiver, Wiring

if TYPE_CHECKING:
    from collections.abc import Sequence

    from emberwake.engine.ecs import World

FLUSH = 0.5
"""How close, in px, counts as resting on a platform."""
TOLERANCE = 1e-4
"""How far short of its step a carried rider may fall before it counts as blocked."""

type Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class PlatformTuning:
    """Lifts and platforms (content/feel.toml, ``[platforms]``)."""

    speed: float = 48.0
    """px/s along the path."""
    dwell: float = 0.8
    """Seconds a looping platform rests at each end."""


@component
@dataclass(slots=True)
class Platform:
    """A solid box on a path: home, then each node of `path` in turn."""

    path: list[str] = field(default_factory=list)
    """Iids of the PathNodes, in this room."""
    speed: float = 0.0
    """px/s; 0 uses the tuning."""
    points: list[Point] = field(default_factory=list)
    """Top-left corners along the path, home first; filled once the nodes have spawned."""


@component
@dataclass(slots=True)
class PlatformRest:
    """How far along its path a platform is. Saved by iid."""

    s: float = 0.0
    """Distance travelled from home, px."""
    forward: bool = True
    """A looping platform's direction."""
    wait: float = 0.0
    """Seconds left of a looping platform's rest."""


@component
@dataclass(slots=True)
class Rider:
    """A box that a platform carries while it rests on one."""


def platform_solids(world: World) -> list[Body]:
    """The boxes the player's and the crates' collision treat as solid."""
    return [body for _, body, _ in world.query(Body, Platform)]


def length(points: Sequence[Point]) -> float:
    """Total length of the path, px."""
    return sum(math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in pairwise(points))


def point_at(points: Sequence[Point], s: float) -> Point:
    """Where a platform `s` px along the path is."""
    for (ax, ay), (bx, by) in pairwise(points):
        span = math.hypot(bx - ax, by - ay)
        if span and s <= span:
            return ax + (bx - ax) * s / span, ay + (by - ay) * s / span
        s -= span
    return points[-1]


def platform_system(world: World, dt: float) -> None:
    """Advance every platform along its path, carrying its riders, unless something blocks it."""
    tuning, wiring, grid = (
        world.resource(PlatformTuning),
        world.resource(Wiring),
        world.resource(TileSource),
    )
    platforms = sorted(
        world.query(Identity, Body, Platform, PlatformRest), key=lambda found: found[1].iid
    )
    for eid, identity, body, platform, rest in platforms:
        if not _place(world, body, platform, rest):
            continue
        total = length(platform.points)
        speed = (platform.speed or tuning.speed) * dt
        if identity.iid in wiring.sources:
            receiver = world.find(eid, Receiver)
            goal = total if receiver is not None and receiver.powered else 0.0
            s = rest.s + max(-speed, min(speed, goal - rest.s))
            forward, wait = rest.forward, rest.wait
        else:
            s, forward, wait = _loop(rest, total, speed, dt, tuning.dwell)
        x, y = point_at(platform.points, s)
        if (x, y) == (body.x, body.y) or _step(world, grid, body, x, y):
            rest.s, rest.forward, rest.wait = s, forward, wait


def _place(world: World, body: Body, platform: Platform, rest: PlatformRest) -> bool:
    """Fill the path from its nodes and move the platform to where it was left."""
    if platform.points:
        return True
    spawner = world.resource(Spawner)
    nodes = [spawner.resolve(iid) for iid in platform.path]
    bodies = [world.find(eid, Body) if eid is not None else None for eid in nodes]
    if not bodies or any(node is None for node in bodies):
        return False
    platform.points = [(body.x, body.y), *((node.x, node.y) for node in bodies if node is not None)]
    rest.s = max(0.0, min(rest.s, length(platform.points)))
    body.x, body.y = point_at(platform.points, rest.s)
    return True


def _loop(
    rest: PlatformRest, total: float, step: float, dt: float, dwell: float
) -> tuple[float, bool, float]:
    """The distance, direction and rest of an unwired platform after this tick."""
    if rest.wait > 0:
        return rest.s, rest.forward, max(0.0, rest.wait - dt)
    s = rest.s + (step if rest.forward else -step)
    if s >= total:
        return total, False, dwell
    if s <= 0:
        return 0.0, True, dwell
    return s, rest.forward, 0.0


def _on_top(rider: Body, base: Body) -> bool:
    return (
        abs(rider.bottom - base.y) <= FLUSH
        and rider.x < base.x + base.width - EPSILON
        and base.x < rider.x + rider.width - EPSILON
    )


def _among(box: Body, boxes: Sequence[Body]) -> bool:
    return any(box is other for other in boxes)


def _step(world: World, grid: TileSource, body: Body, x: float, y: float) -> bool:
    """Carry the riders and take the step to (`x`, `y`), or change nothing and say no."""
    boxes = [(box, True) for _, box, _ in world.query(Body, Rider)]
    boxes += [(box, motor.vy >= 0) for _, box, motor in world.query(Body, Motor) if not motor.dead]
    riders: list[Body] = []
    bases = [body]
    while bases:
        base = bases.pop()
        for box, rides in boxes:
            if rides and not _among(box, riders) and _on_top(box, base):
                riders.append(box)
                bases.append(box)
    others = [box for box, _ in boxes if not _among(box, riders)]
    others += [other for _, other, _ in world.query(Body, Platform) if other is not body]
    dx, dy = x - body.x, y - body.y
    before = [(rider.x, rider.y) for rider in riders]
    for rider in riders:
        move(grid, rider, dx, dy, solids=others)
    carried = all(
        abs(rider.x - ox - dx) < TOLERANCE and abs(rider.y - oy - dy) < TOLERANCE
        for rider, (ox, oy) in zip(riders, before, strict=True)
    )
    if carried and not overlaps(grid, x, y, body.width, body.height, solids=others):
        body.x, body.y = x, y
        return True
    for rider, (ox, oy) in zip(riders, before, strict=True):
        rider.x, rider.y = ox, oy
    return False
