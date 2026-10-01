"""Procedural legs: two-bone inverse kinematics and foot planting.

`two_bone` finds joint angles that put a foot on a target. `Leg` plants a foot on the ground and
takes a lifted step only when the body has moved away from it, and `Gait` limits how many legs of
a creature step at once, so it always keeps feet down. The angles feed a `Rig` pose directly.

Angles are degrees, clockwise on screen with y down, like `emberwake.engine.render.rig`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

type Point = tuple[float, float]

EPSILON = 1e-6


def two_bone(
    origin: Point, target: Point, upper: float, lower: float, *, bend: int = 1
) -> tuple[float, float, bool]:
    """Joint angles that reach `target` with a two-bone limb rooted at `origin`.

    Args:
        origin: The hip (or shoulder).
        target: Where the foot should be.
        upper: Length of the first bone.
        lower: Length of the second bone.
        bend: Which way the knee points, 1 or -1. With 1 the knee bulges counterclockwise of the
            hip-to-foot line (to the right when the foot is straight below the hip).

    Returns:
        ``(upper_angle, lower_angle, reached)``. The upper angle is absolute; the lower is
        relative to the upper, as a child bone's angle is in a `Rig`. When `target` is out of
        reach the limb stretches straight toward it and `reached` is false.
    """
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    distance = math.hypot(dx, dy)
    base = math.degrees(math.atan2(dy, dx))
    reach = upper + lower
    floor = abs(upper - lower)
    clamped = min(max(distance, floor), reach)
    reached = floor <= distance <= reach
    if clamped <= EPSILON:
        return base, 0.0, reached
    cos_hip = (upper * upper + clamped * clamped - lower * lower) / (2 * upper * clamped)
    hip = math.degrees(math.acos(min(max(cos_hip, -1.0), 1.0)))
    cos_knee = (upper * upper + lower * lower - clamped * clamped) / (2 * upper * lower)
    knee = math.degrees(math.acos(min(max(cos_knee, -1.0), 1.0)))
    side = 1 if bend >= 0 else -1
    return base - side * hip, side * (180.0 - knee), reached


def forward(origin: Point, upper: float, lower: float, angles: tuple[float, float]) -> Point:
    """Where the foot ends up for `two_bone`'s angles (for checking and drawing)."""
    a1 = math.radians(angles[0])
    a2 = math.radians(angles[0] + angles[1])
    return (
        origin[0] + upper * math.cos(a1) + lower * math.cos(a2),
        origin[1] + upper * math.sin(a1) + lower * math.sin(a2),
    )


def knee(origin: Point, upper: float, angle: float) -> Point:
    """Where the knee is for an upper-bone `angle`."""
    rad = math.radians(angle)
    return origin[0] + upper * math.cos(rad), origin[1] + upper * math.sin(rad)


@dataclass(slots=True)
class Leg:
    """One leg: a hip offset on the body, bone lengths and stepping behavior.

    Attributes:
        hip: Where the hip sits relative to the body origin.
        upper: Upper bone length.
        lower: Lower bone length.
        reach: Natural stance: how far below the hip, and ahead of it, the foot likes to be.
        step_distance: How far the foot may lag its ideal spot before it must step.
        step_time: Seconds a step takes.
        lift: Height the foot rises mid-step.
        bend: Knee direction, 1 or -1.
    """

    hip: Point = (0.0, 0.0)
    upper: float = 12.0
    lower: float = 12.0
    reach: Point = (0.0, 20.0)
    step_distance: float = 8.0
    step_time: float = 0.25
    lift: float = 5.0
    bend: int = 1
    foot: Point | None = None
    stepping: bool = False
    _from: Point = field(default=(0.0, 0.0), repr=False)
    _to: Point = field(default=(0.0, 0.0), repr=False)
    _t: float = field(default=0.0, repr=False)

    def ideal(self, body: Point, heading: float, ground: Callable[[float], float]) -> Point:
        """Where the foot would like to be: ahead of the hip along `heading`, on the ground."""
        x = body[0] + self.hip[0] + self.reach[0] + heading * self.step_distance * 0.5
        hip_y = body[1] + self.hip[1]
        return x, min(ground(x), hip_y + self.upper + self.lower)

    def lag(self, body: Point, heading: float, ground: Callable[[float], float]) -> float:
        """How far the planted foot is from its ideal spot."""
        if self.foot is None:
            return 0.0
        ix, iy = self.ideal(body, heading, ground)
        return math.hypot(self.foot[0] - ix, self.foot[1] - iy)

    def start_step(self, body: Point, heading: float, ground: Callable[[float], float]) -> None:
        """Lift the foot toward its ideal spot."""
        if self.foot is None:
            self.foot = self.ideal(body, heading, ground)
            return
        self._from, self._to = self.foot, self.ideal(body, heading, ground)
        self._t, self.stepping = 0.0, True

    def update(self, dt: float) -> None:
        """Move a stepping foot along its arc."""
        if not self.stepping:
            return
        self._t = min(self._t + dt / self.step_time, 1.0)
        t = self._t
        x = self._from[0] + (self._to[0] - self._from[0]) * t
        y = self._from[1] + (self._to[1] - self._from[1]) * t - math.sin(math.pi * t) * self.lift
        self.foot = (x, y)
        if t >= 1.0:
            self.foot, self.stepping = self._to, False

    def angles(self, body: Point) -> tuple[float, float, bool]:
        """Joint angles for the foot's current position."""
        hip = (body[0] + self.hip[0], body[1] + self.hip[1])
        return two_bone(hip, self.foot or hip, self.upper, self.lower, bend=self.bend)


class Gait:
    """Several legs that take turns stepping.

    At most `max_stepping` legs are in the air at once; the leg lagging furthest steps first, so
    the creature never lifts all its feet together.
    """

    def __init__(self, legs: Sequence[Leg], max_stepping: int = 1) -> None:
        self.legs = list(legs)
        self.max_stepping = max_stepping

    def update(
        self, body: Point, heading: float, ground: Callable[[float], float], dt: float
    ) -> None:
        """Advance every leg for a body at `body` moving in direction `heading` (-1 to 1)."""
        for leg in self.legs:
            if leg.foot is None:
                leg.start_step(body, heading, ground)
        for leg in self.legs:
            leg.update(dt)
        airborne = sum(leg.stepping for leg in self.legs)
        waiting = sorted(
            (leg for leg in self.legs if not leg.stepping),
            key=lambda leg: -leg.lag(body, heading, ground),
        )
        for leg in waiting:
            if airborne >= self.max_stepping:
                break
            if leg.lag(body, heading, ground) > leg.step_distance:
                leg.start_step(body, heading, ground)
                airborne += 1
