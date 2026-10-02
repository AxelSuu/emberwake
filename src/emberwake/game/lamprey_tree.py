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
from emberwake.engine.physics import move
from emberwake.game.lamprey import (
    Bitten,
    Ctx,
    brightest,
    set_mode,
    steer,
    swim_to,
)

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
    return Tree(Selector(Sequence(Condition(in_phase(1)), lure_cycle()), Action(circle)))


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


# Conditions


def has_bait(c: Ctx) -> bool:
    """Aim at the brightest light, if there is one."""
    c.bb.target = brightest(c)
    return c.bb.target is not None


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
