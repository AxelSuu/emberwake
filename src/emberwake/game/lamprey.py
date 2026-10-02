"""The Lamprey: the Cistern's boss, a head that hunts the brightest light.

This module holds what the fight is made of: tuning, the `Lamprey` component (the tree's
blackboard), its modes and what each means for combat, the events it publishes, and the helpers
the tree's leaves share (finding bait, swimming). The tree is in `lamprey_tree`, the system that
ticks it in `lamprey_system`. Rules: docs/specs/lamprey.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from emberwake.engine.core.bt import Tree
from emberwake.engine.ecs import EntityId, World, component
from emberwake.engine.physics import Body
from emberwake.engine.world.rooms import WorldGrid
from emberwake.game.beacons import Beacon
from emberwake.game.flares import Flare
from emberwake.game.interact import player_body
from emberwake.game.lamps import Lamp
from emberwake.game.light import LightSource
from emberwake.game.switches import Brazier

DRAINED = "lamprey_drained"
"""Save flag: the arena's water is gone. Cleared whenever the fight starts over."""
DEFEATED = "lamprey_defeated"
"""Save flag: the Lamprey is dead. The story beats (#138) read it."""
FLAGS = (DRAINED, DEFEATED)

type Rect = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class LampreyTuning:
    """Numbers for the Lamprey (content/feel.toml, ``[lamprey]``): px, px/s, seconds."""

    hp: int = 18
    iframes: float = 0.35
    contact_damage: int = 1
    knockback: float = 160.0
    bait_flare: float = 1.0
    bait_lamp: float = 0.9
    """Also what lit braziers and beacons weigh."""
    bait_lantern: float = 0.5
    depth: float = 28.0
    """How far under the water line the head swims."""
    swim_speed: float = 130.0
    rise_time: float = 0.5
    stalk_time: float = 1.0
    lunge_speed: float = 300.0
    lunge_range: float = 320.0
    stun_time: float = 2.5
    recover_time: float = 0.6
    rest_time: float = 1.0
    warn_time: float = 0.8
    breach_time: float = 1.4
    breach_span: float = 88.0
    snuff_reach: float = 24.0
    thrash_speed: float = 150.0
    thrash_time: float = 1.6
    gasp_time: float = 1.2


@dataclass(frozen=True, slots=True)
class Mode:
    """What a mode means for combat."""

    submerged: bool = False
    """Under the water: it cannot be hit and does not hurt."""
    harmless: bool = False
    """Contact does not hurt."""
    armor: str = "full"
    """``full`` guards every side, ``crown`` all but from above, ``off`` none."""


MODES = {
    "swim": Mode(submerged=True),
    "warn": Mode(submerged=True),
    "surface": Mode(),
    "lunge": Mode(),
    "recover": Mode(),
    "stunned": Mode(harmless=True, armor="off"),
    "dazed": Mode(harmless=True),
    "breach": Mode(armor="crown"),
    "slump": Mode(harmless=True),
    "thrash": Mode(),
    "gasp": Mode(harmless=True, armor="off"),
}


@component
@dataclass(slots=True)
class Lamprey:
    """The Lamprey's state: what its tree reads and writes."""

    phase: int = 1
    mode: str = "swim"
    since: float = 0.0
    """Seconds in `mode`."""
    home: tuple[float, float] = (0.0, 0.0)
    """Centre of the head at the water line, where it was placed."""
    arena: Rect | None = None
    """The room it fights in (x, y, width, height); the fight runs while the player is in it."""
    facing: int = 1
    heading: float = 0.0
    """Degrees the head tilts from level toward where it moves, up negative."""
    target: tuple[float, float] | None = None
    start: tuple[float, float] = (0.0, 0.0)
    aim: tuple[float, float] = (0.0, -1.0)
    """Unit vector of the lunge."""
    """Where the last lunge or breach began."""
    travelled: float = 0.0
    bit: bool = False
    """The last lunge ended in stone."""
    side: int = 1
    """Which way the next breach goes."""
    drained: bool = False
    casings: list[EntityId] = field(default_factory=list)
    """Sealed photocells of its arena."""
    broken: list[EntityId] = field(default_factory=list)
    """Casings it has broken this fight."""
    awake: bool = False
    """The player is in its arena, so the fight runs."""
    tree: Tree[Ctx] | None = None


@dataclass(frozen=True, slots=True)
class PhaseChanged:
    phase: int


@dataclass(frozen=True, slots=True)
class Bitten:
    """A lunge ended in stone, at (`x`, `y`)."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Breached:
    """The Lamprey leapt out of the water, or fell back, at (`x`, `y`)."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class CasingBroken:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Drained:
    """Every casing is lit and the arena's water is gone."""


@dataclass(frozen=True, slots=True)
class LampreyDefeated:
    x: float
    y: float


@dataclass(slots=True)
class Ctx:
    """The blackboard of a tick: the Lamprey and what it can see."""

    world: World
    eid: EntityId
    body: Body
    bb: Lamprey
    tuning: LampreyTuning
    grid: WorldGrid
    player: Body | None

    @property
    def centre(self) -> tuple[float, float]:
        return self.body.center_x, self.body.y + self.body.height / 2

    @property
    def deep(self) -> float:
        """Centre height of the head when it swims."""
        return self.bb.home[1] + self.tuning.depth


def inside(arena: Rect | None, x: float, y: float) -> bool:
    """Whether the point is in `arena`; with no arena everything is."""
    if arena is None:
        return True
    left, top, width, height = arena
    return left <= x < left + width and top <= y < top + height


def set_mode(bb: Lamprey, mode: str) -> None:
    """Switch to `mode`, restarting its clock; the same mode changes nothing."""
    if bb.mode != mode:
        bb.mode, bb.since = mode, 0.0


def place(body: Body, x: float, y: float) -> None:
    """Move the head's centre to (`x`, `y`)."""
    body.x, body.y = x - body.width / 2, y - body.height / 2


def swim_to(ctx: Ctx, point: tuple[float, float], speed: float, dt: float) -> float:
    """Move toward `point` at `speed`, facing the way it goes; returns the distance left."""
    cx, cy = ctx.centre
    dx, dy = point[0] - cx, point[1] - cy
    distance = math.hypot(dx, dy)
    step = min(speed * dt, distance)
    if distance > 1e-6:
        place(ctx.body, cx + dx / distance * step, cy + dy / distance * step)
        steer(ctx.bb, dx, dy)
    return distance - step


def steer(bb: Lamprey, dx: float, dy: float) -> None:
    """Face and tilt the head the way (`dx`, `dy`) points."""
    if abs(dx) > 1.0:
        bb.facing = 1 if dx > 0 else -1
    bb.heading = max(min(math.degrees(math.atan2(dy, abs(dx) or 1e-6)), 80.0), -80.0)


def baits(ctx: Ctx) -> list[tuple[float, float, float]]:
    """Every light in the arena it would go for, as (x, y, weight times strength)."""
    world, tuning, arena = ctx.world, ctx.tuning, ctx.bb.arena
    found: list[tuple[float, float, float]] = []

    def add(body: Body, weight: float) -> None:
        x, y = body.center_x, body.y + body.height / 2
        if inside(arena, x, y):
            found.append((x, y, weight))

    for _, body, lamp in world.query(Body, Lamp):
        if lamp.lit:
            add(body, tuning.bait_lamp)
    for _, body, brazier in world.query(Body, Brazier):
        if brazier.lit:
            add(body, tuning.bait_lamp)
    for _, body, beacon in world.query(Body, Beacon):
        if beacon.lit:
            add(body, tuning.bait_lamp)
    for _, body, _flare, light in world.query(Body, Flare, LightSource):
        if light.strength > 0:
            add(body, tuning.bait_flare * light.strength)
    player = player_body(world)
    if player is not None:
        add(player, tuning.bait_lantern)
    return found


def brightest(ctx: Ctx) -> tuple[float, float] | None:
    """Where the brightest light of the arena is; the nearest of equals."""
    cx, cy = ctx.centre
    best = min(
        baits(ctx),
        key=lambda bait: (-bait[2], math.hypot(bait[0] - cx, bait[1] - cy), bait[0], bait[1]),
        default=None,
    )
    return None if best is None else (best[0], best[1])


def phase_for(current: int, maximum: int) -> int:
    """The phase hit points left put it in: thirds of its health."""
    if current * 3 > maximum * 2:
        return 1
    return 2 if current * 3 > maximum else 3
