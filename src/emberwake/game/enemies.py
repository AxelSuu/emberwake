"""Enemies: finite-state brains and six kinds, built on health, hit boxes and light.

- **Clockrat** patrols, turns at walls and ledges, and charges when it sees the player.
- **Gloomcrawler** is a creature of shadow: it creeps toward the player, burns in light and flees
  strong light.
- **Wisp-eater** drifts toward light and swoops at the player, then retreats. It hunts lit lamps
  and snuffs them unless a beacon protects them.
- **Drip Lurker** hangs from a dark ceiling, drops on the player below and climbs back; light
  makes it retract.
- **Gearbug** patrols behind an armored front and vents on a cycle, open while it does.

- **Clockrat King** is an elite: armored on every side but above, it charges and calls rats, and
  a hit on the crown topples it.

Rules for the last three: docs/specs/drip-lurker-gearbug.md, docs/specs/clockrat-king.md.

An entity needs only a `Body` and a `Brain`; the system gives it health, a hurt box and a
contact hit box on its first tick.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.fsm import Fsm
from emberwake.engine.ecs import EntityId, World, component
from emberwake.engine.physics import Body, Tile, move, overlaps
from emberwake.engine.world.rooms import WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game.beacons import Beacon
from emberwake.game.combat import (
    Damaged,
    Guard,
    Health,
    Hitbox,
    Hurtbox,
    Killed,
    Knockback,
    Team,
)
from emberwake.game.components import Sprite
from emberwake.game.interact import player_body
from emberwake.game.lamps import nearest_prey, snuff
from emberwake.game.light import LightSource, LightTuning, falloff, light_at
from emberwake.game.player.swing import SwingTuning

GRAVITY = 600.0
MAX_FALL = 300.0
STAGGER_DRAG = 6.0
"""Share of a knock's speed lost per second."""
STANDABLE = frozenset({Tile.SOLID, Tile.ONE_WAY})


@dataclass(frozen=True, slots=True)
class EnemyTuning:
    """Numbers for the enemies (content/feel.toml, ``[enemies]``): px, px/s, seconds."""

    player_hp: int = 3
    player_iframes: float = 1.0
    contact_damage: int = 1
    knockback: float = 140.0
    clockrat_hp: int = 2
    clockrat_speed: float = 36.0
    clockrat_charge_speed: float = 110.0
    clockrat_sight: float = 96.0
    clockrat_charge_time: float = 0.8
    clockrat_rest_time: float = 0.7
    gloom_hp: int = 3
    gloom_speed: float = 22.0
    gloom_flee_speed: float = 60.0
    gloom_sight: float = 140.0
    gloom_burn_light: float = 0.25
    """Light level at which it starts to burn."""
    gloom_flee_light: float = 0.5
    """Light level at which it runs."""
    gloom_burn_rate: float = 1.0
    """Hit points lost per second while burning."""
    wisp_hp: int = 2
    wisp_speed: float = 40.0
    wisp_hunt_speed: float = 70.0
    """Speed toward a lamp it means to snuff."""
    wisp_snuff_reach: float = 10.0
    """How close to a lamp's centre it snuffs it."""
    wisp_swoop_speed: float = 130.0
    wisp_sight: float = 110.0
    wisp_attract: float = 140.0
    """How far away it notices light."""
    wisp_swoop_time: float = 0.55
    wisp_retreat_time: float = 1.2
    lurker_hp: int = 2
    lurker_reach: float = 24.0
    """How far sideways of its centre counts as below it."""
    lurker_range: float = 176.0
    """How far down it looks for the player."""
    lurker_rest: float = 1.0
    """Seconds on the ceiling before it may warn again."""
    lurker_warn: float = 0.5
    lurker_light: float = 0.2
    """Light level (the player's own lantern not counted) that makes it retract."""
    lurker_ground_time: float = 1.5
    lurker_climb_speed: float = 70.0
    lurker_climb_max: float = 3.0
    """Seconds of climbing before it is put back home."""
    gearbug_hp: int = 3
    gearbug_speed: float = 20.0
    gearbug_cycle: float = 4.0
    """Seconds of patrol between vents."""
    gearbug_hiss: float = 0.6
    gearbug_vent: float = 1.5
    king_hp: int = 10
    king_speed: float = 28.0
    king_sight: float = 128.0
    king_rear: float = 0.6
    """Seconds of warning before it charges."""
    king_charge_speed: float = 150.0
    king_charge_time: float = 1.2
    king_rest: float = 1.0
    king_alert: float = 224.0
    """How far sideways the player may be for it to call rats."""
    king_summon_every: float = 6.0
    """Seconds of patrol between calls."""
    king_call: float = 1.0
    """Seconds it stands calling before the rats appear."""
    king_summon_count: int = 2
    king_rats_max: int = 3
    king_topple_time: float = 2.5


@component
@dataclass(slots=True)
class Brain:
    """Which enemy this is and where its state machine stands."""

    kind: str = "clockrat"
    state: str = ""
    time: float = 0.0
    """Seconds in the current state."""
    facing: int = -1
    vy: float = 0.0
    burn: float = 0.0
    """Fraction of a hit point lost to light so far."""
    home: tuple[float, float] = (0.0, 0.0)
    target: tuple[float, float] = (0.0, 0.0)
    """Where a swoop is heading."""
    stagger: float = 0.0
    """Seconds left of being knocked about; the brain waits and contact does not hurt."""
    push: tuple[float, float] = (0.0, 0.0)
    """Velocity of the knock, px/s, decaying while staggered."""


@dataclass(frozen=True, slots=True)
class Vented:
    """A Gearbug opened up and let off steam, at its centre."""

    eid: EntityId
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Toppled:
    """A Clockrat King was knocked flat, at its centre."""

    eid: EntityId
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Summoned:
    """A rat was called to the ground at (`x`, `y`), its feet."""

    eid: EntityId
    x: float
    y: float


@component
@dataclass(slots=True)
class RatSpawn:
    """Marks a spot where a Clockrat King's rats appear, for the King in the same room."""


@component
@dataclass(slots=True)
class Court:
    """What a Clockrat King has called: its rats and the dice that place them."""

    rng: random.Random
    rats: list[EntityId] = field(default_factory=list)
    idle: float = 0.0
    """Seconds of patrol since the last call."""
    used: list[tuple[float, float]] = field(default_factory=list)
    """Markers used in this round of calls; every one is used before any repeats."""


@component
@dataclass(slots=True)
class Minion:
    """A rat that belongs to `owner` and goes when it does."""

    owner: EntityId


@dataclass(slots=True)
class Ctx:
    """What a state function sees on one tick."""

    world: World
    eid: EntityId
    body: Body
    brain: Brain
    tuning: EnemyTuning
    grid: WorldGrid
    player: Body | None

    @property
    def centre(self) -> tuple[float, float]:
        return self.body.center_x, self.body.y + self.body.height / 2

    def light(self) -> float:
        return light_at(self.world, *self.centre)

    def ambient(self) -> float:
        """Light at its centre, without the player's lantern."""
        return light_at(self.world, *self.centre, lantern=False)

    def see_player(self, sight: float) -> bool:
        """The player is within `sight` px ahead and roughly level."""
        if self.player is None:
            return False
        dx = self.player.center_x - self.body.center_x
        dy = self.player.y - self.body.y
        return abs(dy) < 28 and abs(dx) <= sight and (dx * self.brain.facing >= 0)

    def toward_player(self) -> int:
        if self.player is None:
            return self.brain.facing
        return 1 if self.player.center_x >= self.body.center_x else -1


def walk(ctx: Ctx, speed: float, dt: float) -> tuple[bool, bool]:
    """Walk along the ground with gravity; returns (hit a wall, ground ahead is missing)."""
    body, brain, grid = ctx.body, ctx.brain, ctx.grid
    brain.vy = min(brain.vy + GRAVITY * dt, MAX_FALL)
    contacts = move(grid, body, brain.facing * speed * dt, brain.vy * dt)
    if contacts.ground or contacts.ceiling:
        brain.vy = 0.0
    wall = contacts.left or contacts.right
    ahead = body.center_x + brain.facing * (body.width / 2 + 2)
    ledge = contacts.ground and not overlaps(
        grid, ahead - 1, body.bottom + 1, 2, 2, kinds=STANDABLE
    )
    return wall, ledge


def turn(brain: Brain) -> None:
    brain.facing = -brain.facing


# Clockrat


def rat_patrol(ctx: Ctx, dt: float, t: float) -> str | None:
    wall, ledge = walk(ctx, ctx.tuning.clockrat_speed, dt)
    if wall or ledge:
        turn(ctx.brain)
    return "charge" if ctx.see_player(ctx.tuning.clockrat_sight) else None


def rat_charge(ctx: Ctx, dt: float, t: float) -> str | None:
    wall, ledge = walk(ctx, ctx.tuning.clockrat_charge_speed, dt)
    if wall or ledge or t >= ctx.tuning.clockrat_charge_time:
        if wall or ledge:
            turn(ctx.brain)
        return "rest"
    return None


def rat_rest(ctx: Ctx, dt: float, t: float) -> str | None:
    walk(ctx, 0.0, dt)
    return "patrol" if t >= ctx.tuning.clockrat_rest_time else None


CLOCKRAT: Fsm[Ctx] = Fsm({"patrol": rat_patrol, "charge": rat_charge, "rest": rat_rest})


# Gloomcrawler


def nearest_light_side(ctx: Ctx) -> int:
    """Which way (-1 or 1) the strongest light near the enemy lies."""
    world, (x, y) = ctx.world, ctx.centre
    tuning = world.resource(LightTuning)
    best, side = 0.0, 0
    candidates: list[tuple[float, float, float, float]] = []
    for _, body, beacon in world.query(Body, Beacon):
        if beacon.lit:
            candidates.append((body.center_x, body.y, tuning.beacon_radius, 1.0))
    for _, body, source in world.query(Body, LightSource):
        candidates.append((body.center_x, body.y, source.radius, source.strength))
    if ctx.player is not None:
        candidates.append((ctx.player.center_x, ctx.player.y, tuning.lantern_radius, 1.0))
    for cx, cy, radius, strength in candidates:
        level = falloff(math.hypot(x - cx, y - cy), radius, strength)
        if level > best:
            best, side = level, 1 if cx >= x else -1
    return side


def gloom_creep(ctx: Ctx, dt: float, t: float) -> str | None:
    t_ = ctx.tuning
    if ctx.light() >= t_.gloom_flee_light:
        return "flee"
    if ctx.player is not None and abs(ctx.player.center_x - ctx.body.center_x) < t_.gloom_sight:
        ctx.brain.facing = ctx.toward_player()
    wall, ledge = walk(ctx, t_.gloom_speed, dt)
    if wall or ledge:
        turn(ctx.brain)
    return None


def gloom_flee(ctx: Ctx, dt: float, t: float) -> str | None:
    t_ = ctx.tuning
    side = nearest_light_side(ctx)
    ctx.brain.facing = -side if side else ctx.brain.facing
    wall, ledge = walk(ctx, t_.gloom_flee_speed, dt)
    if wall or ledge:
        walk(ctx, 0.0, dt)
    return "creep" if ctx.light() < t_.gloom_flee_light * 0.6 else None


GLOOMCRAWLER: Fsm[Ctx] = Fsm({"creep": gloom_creep, "flee": gloom_flee})


# Wisp-eater


def fly(ctx: Ctx, dx: float, dy: float) -> None:
    move(ctx.grid, ctx.body, dx, dy)


def toward(ctx: Ctx, point: tuple[float, float], speed: float, dt: float) -> float:
    """Fly toward `point` at `speed`; returns the distance left."""
    cx, cy = ctx.centre
    dx, dy = point[0] - cx, point[1] - cy
    dist = math.hypot(dx, dy)
    if dist > 1e-6:
        step = min(speed * dt, dist)
        fly(ctx, dx / dist * step, dy / dist * step)
    return dist


def brightest_light(ctx: Ctx, radius: float) -> tuple[float, float] | None:
    """Position of the nearest light source or lit beacon within `radius`."""
    x, y = ctx.centre
    best: tuple[float, tuple[float, float]] | None = None
    sources = [
        (b.center_x, b.y) for _, b, beacon in ctx.world.query(Body, Beacon) if beacon.lit
    ] + [(b.center_x, b.y) for _, b, _s in ctx.world.query(Body, LightSource)]
    for sx, sy in sources:
        d = math.hypot(x - sx, y - sy)
        if d <= radius and (best is None or d < best[0]):
            best = (d, (sx, sy))
    return best[1] if best else None


def wisp_notices_player(ctx: Ctx) -> bool:
    """Aims a swoop at the player and returns True if they are within sight."""
    player, brain = ctx.player, ctx.brain
    if player is None:
        return False
    cx, cy = ctx.centre
    if math.hypot(player.center_x - cx, player.y - cy) > ctx.tuning.wisp_sight:
        return False
    brain.target = (player.center_x, player.y + player.height / 2)
    return True


def wisp_hover(ctx: Ctx, dt: float, t: float) -> str | None:
    t_, brain = ctx.tuning, ctx.brain
    if wisp_notices_player(ctx):
        return "swoop"
    if nearest_prey(ctx.world, *ctx.centre, t_.wisp_attract) is not None:
        return "hunt"
    light = brightest_light(ctx, t_.wisp_attract)
    if light is not None:
        toward(ctx, (light[0], light[1] - 18), t_.wisp_speed, dt)
    else:
        bob = (brain.home[0], brain.home[1] + math.sin(t * 2.0) * 6)
        toward(ctx, bob, t_.wisp_speed * 0.5, dt)
    return None


def wisp_hunt(ctx: Ctx, dt: float, t: float) -> str | None:
    """Fly at the nearest lit, unprotected lamp and snuff it on arrival."""
    t_ = ctx.tuning
    if wisp_notices_player(ctx):
        return "swoop"
    prey = nearest_prey(ctx.world, *ctx.centre, t_.wisp_attract)
    if prey is None:
        return "hover"
    lamp = ctx.world.get(prey, Body)
    left = toward(ctx, (lamp.center_x, lamp.y + lamp.height / 2), t_.wisp_hunt_speed, dt)
    if left <= t_.wisp_snuff_reach:
        snuff(ctx.world, prey)
        return "retreat"
    return None


def wisp_swoop(ctx: Ctx, dt: float, t: float) -> str | None:
    left = toward(ctx, ctx.brain.target, ctx.tuning.wisp_swoop_speed, dt)
    return "retreat" if t >= ctx.tuning.wisp_swoop_time or left < 3 else None


def wisp_retreat(ctx: Ctx, dt: float, t: float) -> str | None:
    toward(ctx, ctx.brain.home, ctx.tuning.wisp_speed, dt)
    return "hover" if t >= ctx.tuning.wisp_retreat_time else None


WISP_EATER: Fsm[Ctx] = Fsm(
    {"hover": wisp_hover, "hunt": wisp_hunt, "swoop": wisp_swoop, "retreat": wisp_retreat}
)


# Drip Lurker


def lurker_below(ctx: Ctx) -> bool:
    """The player is under it, within reach and range, with nothing to land on in between."""
    player, body, t = ctx.player, ctx.body, ctx.tuning
    if player is None or abs(player.center_x - body.center_x) > t.lurker_reach:
        return False
    drop = player.y - body.bottom
    if drop < -4 or drop > t.lurker_range:
        return False
    return not overlaps(ctx.grid, body.x, body.bottom, body.width, max(drop, 1.0), kinds=STANDABLE)


def lurker_lit(ctx: Ctx) -> bool:
    return ctx.ambient() >= ctx.tuning.lurker_light


def lurker_ceiling(ctx: Ctx, dt: float, t: float) -> str | None:
    if lurker_lit(ctx):
        return "retract"
    return "warn" if t >= ctx.tuning.lurker_rest and lurker_below(ctx) else None


def lurker_warn(ctx: Ctx, dt: float, t: float) -> str | None:
    if lurker_lit(ctx):
        return "retract"
    return "drop" if t >= ctx.tuning.lurker_warn else None


def settle(ctx: Ctx, dt: float) -> bool:
    """Fall under gravity; returns whether it is on the ground."""
    brain = ctx.brain
    brain.vy = min(brain.vy + GRAVITY * dt, MAX_FALL)
    contacts = move(ctx.grid, ctx.body, 0.0, brain.vy * dt)
    if contacts.ground or contacts.ceiling:
        brain.vy = 0.0
    return contacts.ground


def lurker_drop(ctx: Ctx, dt: float, t: float) -> str | None:
    return "ground" if settle(ctx, dt) else None


def lurker_ground(ctx: Ctx, dt: float, t: float) -> str | None:
    settle(ctx, dt)
    return "climb" if t >= ctx.tuning.lurker_ground_time or lurker_lit(ctx) else None


def lurker_climb(ctx: Ctx, dt: float, t: float) -> str | None:
    left = toward(ctx, ctx.brain.home, ctx.tuning.lurker_climb_speed, dt)
    if left > 2.0 and t < ctx.tuning.lurker_climb_max:
        return None
    body, (x, y) = ctx.body, ctx.brain.home
    body.x, body.y = x - body.width / 2, y - body.height / 2
    ctx.brain.vy = 0.0
    return "ceiling"


def lurker_retract(ctx: Ctx, dt: float, t: float) -> str | None:
    return "ceiling" if ctx.ambient() < ctx.tuning.lurker_light * 0.6 else None


DRIP_LURKER: Fsm[Ctx] = Fsm(
    {
        "ceiling": lurker_ceiling,
        "warn": lurker_warn,
        "drop": lurker_drop,
        "ground": lurker_ground,
        "climb": lurker_climb,
        "retract": lurker_retract,
    }
)


def lurker_guard(brain: Brain) -> int | None:
    return 0 if brain.state == "retract" else None


# Gearbug


def bug_patrol(ctx: Ctx, dt: float, t: float) -> str | None:
    wall, ledge = walk(ctx, ctx.tuning.gearbug_speed, dt)
    if wall or ledge:
        turn(ctx.brain)
    return "hiss" if t >= ctx.tuning.gearbug_cycle else None


def bug_hiss(ctx: Ctx, dt: float, t: float) -> str | None:
    walk(ctx, 0.0, dt)
    if t < ctx.tuning.gearbug_hiss:
        return None
    ctx.world.resource(EventBus).publish(Vented(ctx.eid, *ctx.centre))
    return "vent"


def bug_vent(ctx: Ctx, dt: float, t: float) -> str | None:
    walk(ctx, 0.0, dt)
    return "patrol" if t >= ctx.tuning.gearbug_vent else None


GEARBUG: Fsm[Ctx] = Fsm({"patrol": bug_patrol, "hiss": bug_hiss, "vent": bug_vent})


def gearbug_guard(brain: Brain) -> int | None:
    return None if brain.state == "vent" else brain.facing


# Clockrat King


def king_court(ctx: Ctx) -> Court:
    return ctx.world.get(ctx.eid, Court)


def king_calls(ctx: Ctx) -> bool:
    """A call is due, the player is near and there is room for more rats."""
    t, court = ctx.tuning, king_court(ctx)
    alive = sum(1 for rat in court.rats if ctx.world.reserved(rat))
    near = ctx.player is not None and (abs(ctx.player.center_x - ctx.body.center_x) <= t.king_alert)
    return court.idle >= t.king_summon_every and near and alive < t.king_rats_max


def king_patrol(ctx: Ctx, dt: float, t: float) -> str | None:
    king_court(ctx).idle += dt
    wall, ledge = walk(ctx, ctx.tuning.king_speed, dt)
    if wall or ledge:
        turn(ctx.brain)
    if king_calls(ctx):
        return "call"
    return "rear" if ctx.see_player(ctx.tuning.king_sight) else None


def king_rear(ctx: Ctx, dt: float, t: float) -> str | None:
    ctx.brain.facing = ctx.toward_player()
    walk(ctx, 0.0, dt)
    return "charge" if t >= ctx.tuning.king_rear else None


def king_charge(ctx: Ctx, dt: float, t: float) -> str | None:
    wall, ledge = walk(ctx, ctx.tuning.king_charge_speed, dt)
    if not (wall or ledge or t >= ctx.tuning.king_charge_time):
        return None
    if wall or ledge:
        turn(ctx.brain)
    return "rest"


def king_rest(ctx: Ctx, dt: float, t: float) -> str | None:
    walk(ctx, 0.0, dt)
    return "patrol" if t >= ctx.tuning.king_rest else None


def king_call(ctx: Ctx, dt: float, t: float) -> str | None:
    walk(ctx, 0.0, dt)
    if t < ctx.tuning.king_call:
        return None
    summon(ctx)
    return "patrol"


def summon(ctx: Ctx) -> None:
    """Call rats to the markers of its room: the next unused ones, in dice-rolled order."""
    world, court, t = ctx.world, king_court(ctx), ctx.tuning
    court.idle = 0.0
    court.rats = [rat for rat in court.rats if world.reserved(rat)]
    markers = sorted(
        (body.center_x, body.bottom)
        for eid, body, _ in world.query(Body, RatSpawn)
        if _room(world, eid) == _room(world, ctx.eid)
    )
    bus = world.resource(EventBus)
    for _ in range(min(t.king_summon_count, t.king_rats_max - len(court.rats))):
        free = [m for m in markers if m not in court.used]
        if not free and markers:
            court.used.clear()
            free = markers
        if not free:
            return
        x, y = court.rng.choice(free)
        court.used.append((x, y))
        rat = world.spawn(
            Body(x - 8, y - 16, 16, 16),
            Brain("clockrat", facing=court.rng.choice((-1, 1))),
            Sprite("clockrat"),
            Minion(ctx.eid),
        )
        court.rats.append(rat)
        bus.publish(Summoned(rat, x, y))


def _room(world: World, eid: EntityId) -> str | None:
    identity = world.find(eid, Identity)
    return None if identity is None else identity.room


def king_toppled(ctx: Ctx, dt: float, t: float) -> str | None:
    if t == 0.0:
        ctx.world.resource(EventBus).publish(Toppled(ctx.eid, *ctx.centre))
    settle(ctx, dt)
    return "patrol" if t >= ctx.tuning.king_topple_time else None


CLOCKRAT_KING: Fsm[Ctx] = Fsm(
    {
        "patrol": king_patrol,
        "rear": king_rear,
        "charge": king_charge,
        "rest": king_rest,
        "call": king_call,
        "toppled": king_toppled,
    }
)


def king_guard(brain: Brain) -> int | None:
    return None if brain.state == "toppled" else 0


@dataclass(frozen=True, slots=True)
class Kind:
    fsm: Fsm[Ctx]
    first: str
    hp: str
    """Name of the `EnemyTuning` field holding its hit points."""
    flier: bool = False
    shadow: bool = False
    """Burns in light."""
    guard: Callable[[Brain], int | None] | None = None
    """Which side its armor covers now (0 all, else a facing), or None while it is open."""
    harmless: frozenset[str] = frozenset()
    """States in which contact does not hurt."""
    pinned: dict[str, str] = field(default_factory=dict)
    """States where a hit does not knock it about but moves it to the state given."""
    open: frozenset[str] = frozenset()
    """States drawn with the sprite's active image."""
    directional: bool = False
    """Drawn mirrored when it faces left."""
    crown: bool = False
    """Its all-round armor leaves the top open: a hit from above gets through."""
    heavy: bool = False
    """A hit never knocks it about."""
    dark: frozenset[str] = frozenset()
    """States in which its `LightSource` is out."""
    court: bool = False
    """Calls rats."""
    permanent: bool = False
    """Killed for good: retired by iid, never respawned."""
    size: tuple[int, int] = (16, 16)
    """Body size, px, for one that is not placed in a level."""


KINDS = {
    "clockrat": Kind(CLOCKRAT, "patrol", "clockrat_hp"),
    "gloomcrawler": Kind(GLOOMCRAWLER, "creep", "gloom_hp", shadow=True),
    "wisp_eater": Kind(WISP_EATER, "hover", "wisp_hp", flier=True),
    "drip_lurker": Kind(
        DRIP_LURKER,
        "ceiling",
        "lurker_hp",
        guard=lurker_guard,
        harmless=frozenset({"retract"}),
        pinned={"ceiling": "drop", "warn": "drop"},
        open=frozenset({"retract"}),
    ),
    "gearbug": Kind(
        GEARBUG,
        "patrol",
        "gearbug_hp",
        guard=gearbug_guard,
        open=frozenset({"vent"}),
        directional=True,
    ),
    "clockrat_king": Kind(
        CLOCKRAT_KING,
        "patrol",
        "king_hp",
        guard=king_guard,
        harmless=frozenset({"toppled"}),
        pinned=dict.fromkeys(("patrol", "rear", "charge", "rest", "call"), "toppled"),
        open=frozenset({"toppled"}),
        directional=True,
        crown=True,
        heavy=True,
        dark=frozenset({"toppled"}),
        court=True,
        permanent=True,
        size=(32, 32),
    ),
}


def enemy_system(world: World, dt: float) -> None:
    """Equip new enemies, run every brain one step, burn shadow creatures and clear the dead."""
    tuning, grid = world.resource(EnemyTuning), world.resource(WorldGrid)
    bus, player = world.resource(EventBus), player_body(world)
    for eid, minion in list(world.query(Minion)):
        if minion.owner not in world:
            world.despawn(eid)
    for eid, body, brain in list(world.query(Body, Brain)):
        kind = KINDS[brain.kind]
        if not world.has(eid, Health):
            _equip(world, eid, kind, tuning)
            continue
        health = world.get(eid, Health)
        if health.dead:
            _clear(world, eid, kind)
            continue
        hitbox = world.get(eid, Hitbox)
        hitbox.hit.clear()
        if _stagger(world, eid, body, brain, kind, dt):
            hitbox.active = False
            continue
        ctx = Ctx(world, eid, body, brain, tuning, grid, player)
        state = kind.fsm.step(ctx, brain.state, dt, brain.time)
        brain.time = brain.time + dt if state == brain.state else 0.0
        brain.state = state
        hitbox.active = state not in kind.harmless
        if kind.guard is not None:
            side = kind.guard(brain)
            guard = world.get(eid, Guard)
            guard.active, guard.facing = side is not None, side or 0
        if kind.dark and (lamp := world.find(eid, LightSource)) is not None:
            lamp.strength = 0.0 if state in kind.dark else 1.0
        if kind.shadow:
            _burn(ctx, health, bus, dt)


def _clear(world: World, eid: EntityId, kind: Kind) -> None:
    """Remove a dead enemy and whatever it called; a permanent one is retired by iid."""
    court = world.find(eid, Court)
    for rat in court.rats if court is not None else ():
        world.despawn(rat)
    placed = world.has(eid, Identity) and not world.has(eid, Minion)
    if kind.permanent and placed and world.has_resource(Spawner):
        world.resource(Spawner).retire(eid)
    else:
        world.despawn(eid)


def _stagger(  # noqa: PLR0917
    world: World, eid: EntityId, body: Body, brain: Brain, kind: Kind, dt: float
) -> bool:
    """Take a fresh `Knockback` and slide with it; returns whether the enemy is staggered."""
    knock = world.find(eid, Knockback)
    if knock is not None:
        world.remove(eid, Knockback)
        if brain.state in kind.pinned:
            brain.state, brain.time = kind.pinned[brain.state], 0.0
            return False
        if kind.heavy:
            return False
        brain.push = (knock.vx, knock.vy)
        tuning = world.resource(SwingTuning) if world.has_resource(SwingTuning) else SwingTuning()
        brain.stagger = tuning.stagger
        if not kind.flier:
            brain.vy = knock.vy
    if brain.stagger <= 0:
        return False
    brain.stagger -= dt
    vx, vy = brain.push
    grid = world.resource(WorldGrid)
    if kind.flier:
        move(grid, body, vx * dt, vy * dt)
    else:
        brain.vy = min(brain.vy + GRAVITY * dt, MAX_FALL)
        contacts = move(grid, body, vx * dt, brain.vy * dt)
        if contacts.ground or contacts.ceiling:
            brain.vy = 0.0
    fade = max(1.0 - STAGGER_DRAG * dt, 0.0)
    brain.push = (vx * fade, vy * fade)
    return True


def _equip(world: World, eid: EntityId, kind: Kind, tuning: EnemyTuning) -> None:
    body, brain = world.get(eid, Body), world.get(eid, Brain)
    hp = getattr(tuning, kind.hp)
    brain.state = brain.state or kind.first
    brain.home = (body.center_x, body.y + body.height / 2)
    if kind.guard is not None:
        world.add(eid, Guard(top=not kind.crown))
    if kind.court:
        identity = world.find(eid, Identity)
        world.add(eid, Court(random.Random(identity.iid if identity else kind.first)))
    world.add(
        eid,
        Health(hp, iframes=0.0),
        Hurtbox(Team.ENEMY),
        Hitbox(
            damage=tuning.contact_damage,
            targets=Team.PLAYER,
            size=(body.width, body.height),
            knockback=tuning.knockback,
            active=True,
        ),
    )


def _burn(ctx: Ctx, health: Health, bus: EventBus, dt: float) -> None:
    if ctx.light() < ctx.tuning.gloom_burn_light:
        return
    brain = ctx.brain
    brain.burn += ctx.tuning.gloom_burn_rate * dt
    while brain.burn >= 1.0 and not health.dead:
        brain.burn -= 1.0
        health.current -= 1
        x, y = ctx.centre
        bus.publish(Damaged(ctx.eid, ctx.eid, 1, max(health.current, 0), x, y, 0.0, 0.0))
        if health.current <= 0:
            health.dead = True
            bus.publish(Killed(ctx.eid, ctx.eid))
