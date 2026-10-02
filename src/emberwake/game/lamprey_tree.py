"""The Lamprey's behavior tree: one cycle per phase, built from small leaves.

Leaves read and write the `Lamprey` blackboard through a `Ctx` and move the head directly, so
the same sequence of lights and positions always gives the same fight. A phase change makes
`lamprey_system` reset the tree, and the new phase starts from its first step. Rules:
docs/specs/lamprey.md.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from emberwake.engine.core.bt import (
    FAILURE,
    RUNNING,
    SUCCESS,
    Action,
    Condition,
    Selector,
    Sequence,
    Status,
    Tree,
)
from emberwake.engine.core.events import EventBus
from emberwake.engine.physics import Body, move
from emberwake.game.lamprey import (
    Bitten,
    Breached,
    Ctx,
    Lamprey,
    brightest,
    inside,
    place,
    set_mode,
    steer,
    swim_to,
)
from emberwake.game.lamps import Lamp, nearest_prey, snuff

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.core.bt import Node

MARGIN = 24.0
"""Px from the arena's walls the head keeps to when it comes up under a light."""
ALIGNED = 2.0
"""Px of slack for being under a light."""
DIVE_SPEED = 2.0
"""A dive is this many times a swim."""

type Leaf = Node[Ctx]


def build_tree() -> Tree[Ctx]:
    """A tree for one Lamprey: nodes keep run state, so every Lamprey needs its own."""
    return Tree(
        Selector(
            Sequence(
                Condition(in_phase(3)),
                Selector(
                    Sequence(Condition(is_drained), thrash_cycle()),
                    lure_cycle(armored=True),
                    Action(circle),
                ),
            ),
            Sequence(Condition(in_phase(2)), breach_cycle()),
            Sequence(Condition(in_phase(1)), lure_cycle()),
            Action(circle),
        )
    )


def in_phase(phase: int) -> Callable[[Ctx], bool]:
    return lambda c: c.bb.phase == phase


def lure_cycle(*, armored: bool = False) -> Leaf:
    """Phase 1: come up under a light, stalk it, lunge past it; stone stuns, then dive.

    With `armored` a stunned Lamprey keeps its armor (phase 3, while the water is still there).
    """
    return Sequence(
        Condition(has_bait),
        Action(emerge),
        Action(stalk),
        Action(lunge),
        Selector(
            Sequence(Condition(bit_stone), Action(daze if armored else stun)),
            Action(recover),
        ),
        Action(dive),
        Action(rest),
    )


def breach_cycle() -> Leaf:
    """Phase 2: swim to one side of a lit lamp (else the player), warn, leap over it, rest."""
    return Sequence(
        Condition(has_quarry),
        Action(approach),
        Action(warn),
        Action(breach),
        Action(rest),
    )


def thrash_cycle() -> Leaf:
    """Phase 3, drained: slide at the player on the floor, then gasp, open, for a moment."""
    return Sequence(Action(thrash), Action(gasp))


# Conditions


def has_bait(c: Ctx) -> bool:
    """Aim at the brightest light, if there is one."""
    c.bb.target = brightest(c)
    return c.bb.target is not None


def has_quarry(c: Ctx) -> bool:
    """Aim at the nearest lit lamp it can snuff, else at the player."""
    x, y = c.centre
    lamps = [
        (math.hypot(body.center_x - x, body.y + body.height / 2 - y), eid, body)
        for eid, body, lamp in c.world.query(Body, Lamp)
        if lamp.lit and not lamp.protected and inside(c.bb.arena, body.center_x, body.y)
    ]
    if lamps:
        _, _, body = min(lamps, key=lambda lamp: lamp[:2])
        c.bb.target = (body.center_x, body.y + body.height / 2)
    elif c.player is not None:
        c.bb.target = (c.player.center_x, c.player.y + c.player.height / 2)
    else:
        c.bb.target = None
    return c.bb.target is not None


def is_drained(c: Ctx) -> bool:
    return c.bb.drained


def bit_stone(c: Ctx) -> bool:
    return c.bb.bit


# Leaves


def circle(c: Ctx, dt: float, t: float) -> Status:
    """Nothing to hunt: stay down."""
    set_mode(c.bb, "swim")
    swim_to(c, (c.centre[0], c.deep), c.tuning.swim_speed, dt)
    return RUNNING


def column(c: Ctx, x: float) -> float:
    """`x` kept off the arena's walls."""
    arena = c.bb.arena
    if arena is None:
        return x
    return min(max(x, arena[0] + MARGIN), arena[0] + arena[2] - MARGIN)


def emerge(c: Ctx, dt: float, t: float) -> Status:
    """Swim under the light, then rise until the head is at the water line."""
    bb, tuning = c.bb, c.tuning
    if bb.target is None:
        return FAILURE
    goal, x = column(c, bb.target[0]), c.centre[0]
    if abs(x - goal) > ALIGNED:
        set_mode(bb, "swim")
        swim_to(c, (goal, c.deep), tuning.swim_speed, dt)
        return RUNNING
    left = swim_to(c, (goal, bb.home[1]), tuning.depth / tuning.rise_time, dt)
    set_mode(bb, "surface" if left <= 0 else "swim")
    return SUCCESS if left <= 0 else RUNNING


def stalk(c: Ctx, dt: float, t: float) -> Status:
    """Hover at the water line, following the light, lure swaying."""
    bb = c.bb
    set_mode(bb, "surface")
    if (target := brightest(c)) is not None:
        bb.target = target
        swim_to(c, (column(c, target[0]), bb.home[1]), c.tuning.swim_speed * 0.5, dt)
    return SUCCESS if t >= c.tuning.stalk_time else RUNNING


def approach(c: Ctx, dt: float, t: float) -> Status:
    """Swim under the point a breach starts from, to one side of the quarry."""
    bb, tuning = c.bb, c.tuning
    if bb.target is None:
        return FAILURE
    set_mode(bb, "swim")
    goal = (column(c, bb.target[0] - bb.side * tuning.breach_span), c.deep)
    return SUCCESS if swim_to(c, goal, tuning.swim_speed, dt) <= 0 else RUNNING


def warn(c: Ctx, dt: float, t: float) -> Status:
    """Ripples and a bobbing lure under the water."""
    set_mode(c.bb, "warn")
    return SUCCESS if t >= c.tuning.warn_time else RUNNING


def breach(c: Ctx, dt: float, t: float) -> Status:
    """Leap in an arc whose top is at the quarry, snuffing the lamps it passes."""
    bb, tuning = c.bb, c.tuning
    if bb.target is None:
        return FAILURE
    x0, tx, ty = bb.start[0] if t else c.centre[0], *bb.target
    if t == 0.0:
        bb.start = c.centre
    top = max(min(ty, bb.home[1] - tuning.depth), _ceiling(bb))
    s = min((t + dt) / tuning.breach_time, 1.0)
    x1 = x0 + 2 * (tx - x0)
    lift = c.deep - top
    place(c.body, x0 + (x1 - x0) * s, c.deep - lift * 4 * s * (1 - s))
    steer(bb, x1 - x0, -lift * 4 * (1 - 2 * s))
    out = c.centre[1] < bb.home[1]
    bus = c.world.resource(EventBus)
    if out != (bb.mode == "breach"):
        bus.publish(Breached(*c.centre))
    set_mode(bb, "breach" if out else "swim")
    if out and (prey := nearest_prey(c.world, *c.centre, tuning.snuff_reach)) is not None:
        snuff(c.world, prey)
    if s < 1.0:
        return RUNNING
    bb.side = -bb.side
    return SUCCESS


def _ceiling(bb: Lamprey) -> float:
    return bb.arena[1] + MARGIN if bb.arena is not None else -math.inf


def lunge(c: Ctx, dt: float, t: float) -> Status:
    """Dash at the light and on past it, until stone stops the head or the range runs out."""
    bb, tuning = c.bb, c.tuning
    if t == 0.0:
        x, y = c.centre
        goal = brightest(c) or bb.target or (x, y - 1.0)
        dx, dy = goal[0] - x, goal[1] - y
        length = math.hypot(dx, dy) or 1.0
        bb.aim = (dx / length, dy / length)
        bb.start, bb.travelled, bb.bit = (x, y), 0.0, False
        steer(bb, *bb.aim)
    set_mode(bb, "lunge")
    step = tuning.lunge_speed * dt
    contacts = move(c.grid, c.body, bb.aim[0] * step, bb.aim[1] * step)
    bb.travelled += step
    floor = contacts.ground and not contacts.one_way
    if contacts.left or contacts.right or contacts.ceiling or floor:
        bb.bit = True
        c.world.resource(EventBus).publish(Bitten(*c.centre))
        return SUCCESS
    return SUCCESS if bb.travelled >= tuning.lunge_range else RUNNING


def stun(c: Ctx, dt: float, t: float) -> Status:
    """Stuck in the stone: open and harmless."""
    set_mode(c.bb, "stunned")
    return SUCCESS if t >= c.tuning.stun_time else RUNNING


def daze(c: Ctx, dt: float, t: float) -> Status:
    """Stuck in the stone, armor up (the water is still there)."""
    set_mode(c.bb, "dazed")
    return SUCCESS if t >= c.tuning.stun_time else RUNNING


def recover(c: Ctx, dt: float, t: float) -> Status:
    """Hanging in the air after a miss."""
    set_mode(c.bb, "recover")
    return SUCCESS if t >= c.tuning.recover_time else RUNNING


def dive(c: Ctx, dt: float, t: float) -> Status:
    """Fall back into the water; it counts as under once the head passes the line."""
    bb, tuning = c.bb, c.tuning
    set_mode(bb, "recover" if c.centre[1] < bb.home[1] else "swim")
    left = swim_to(c, (c.centre[0], c.deep), tuning.swim_speed * DIVE_SPEED, dt)
    return SUCCESS if left <= 0 else RUNNING


def rest(c: Ctx, dt: float, t: float) -> Status:
    set_mode(c.bb, "swim")
    return SUCCESS if t >= c.tuning.rest_time else RUNNING


def thrash(c: Ctx, dt: float, t: float) -> Status:
    """Slide along the floor at the player: armored, and it hurts."""
    set_mode(c.bb, "thrash")
    if c.player is not None:
        goal = column(c, c.player.center_x)
        swim_to(c, (goal, c.bb.home[1]), c.tuning.thrash_speed, dt)
    return SUCCESS if t >= c.tuning.thrash_time else RUNNING


def gasp(c: Ctx, dt: float, t: float) -> Status:
    """Stopped and open: the window to hit its head."""
    set_mode(c.bb, "gasp")
    return SUCCESS if t >= c.tuning.gasp_time else RUNNING
