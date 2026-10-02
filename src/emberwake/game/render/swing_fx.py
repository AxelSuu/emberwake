"""How a swing looks: the lantern's path around the player and the arc of light it leaves.

The lantern sweeps from a start to an end angle while the hitbox is active, then settles back
to where it hangs. Angles are degrees on screen (0 right, 90 down) for a player facing right.
"""

from __future__ import annotations

import functools
import math

import pygame

from emberwake.engine.core.mathx import clamp
from emberwake.game import palette
from emberwake.game.player.swing import Direction, Swing, SwingTuning

SWEEPS = {
    Direction.FORWARD: (-80.0, 70.0),
    Direction.UP: (-165.0, -15.0),
    Direction.DOWN: (15.0, 165.0),
}
RADIUS = 14.0
"""Distance of the lantern from the shoulder at full reach, px."""
TRAIL_STEPS = 8
TRAIL_SIZE = 48
ARM = pygame.Color("#323353")
_HOT = pygame.Color(palette.EMBER_HOT)
_CORE = pygame.Color(palette.EMBER_CORE)


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _sweep(direction: Direction, facing: int) -> tuple[float, float]:
    start, end = SWEEPS[direction]
    if facing < 0:
        start, end = 180.0 - start, 180.0 - end
    return start, end


def sweep_angle(swing: Swing, tuning: SwingTuning) -> float:
    """The lantern's angle now; it waits at the start during windup."""
    start, end = _sweep(swing.direction, swing.facing)
    t = clamp((swing.tick - tuning.windup) / max(tuning.active, 1), 0.0, 1.0)
    return start + (end - start) * _ease_out(t)


def lantern_point(
    swing: Swing,
    tuning: SwingTuning,
    shoulder: tuple[float, float],
    rest: tuple[float, float],
) -> tuple[float, float]:
    """Where the lantern is: on the sweep, then easing back to `rest` during recovery."""
    angle = math.radians(sweep_angle(swing, tuning))
    x = shoulder[0] + math.cos(angle) * RADIUS
    y = shoulder[1] + math.sin(angle) * RADIUS
    back = (swing.tick - tuning.windup - tuning.active) / max(tuning.recovery, 1)
    if back <= 0:
        return x, y
    back = _ease_out(clamp(back, 0.0, 1.0))
    return x + (rest[0] - x) * back, y + (rest[1] - y) * back


def trail(swing: Swing, tuning: SwingTuning) -> pygame.Surface | None:
    """The arc of light behind the lantern, centred on the shoulder; None once it has faded."""
    since = swing.tick - tuning.windup
    fade_ticks = tuning.active + 3
    if since <= 0 or since > fade_ticks:
        return None
    t = clamp(since / max(tuning.active, 1), 0.0, 1.0)
    reach = round(t * TRAIL_STEPS)
    fade = round((1.0 - max(since - tuning.active, 0) / 4) * TRAIL_STEPS)
    return _trail(swing.direction, swing.facing, reach, fade)


@functools.cache
def _trail(direction: Direction, facing: int, reach: int, fade: int) -> pygame.Surface:
    image = pygame.Surface((TRAIL_SIZE, TRAIL_SIZE), pygame.SRCALPHA)
    start, end = _sweep(direction, facing)
    centre = TRAIL_SIZE / 2
    alpha = round(200 * fade / TRAIL_STEPS)
    steps = max(reach * 8, 1)
    for i in range(steps + 1):
        u = i / steps
        angle = math.radians(start + (end - start) * _ease_out(u * reach / TRAIL_STEPS))
        for radius, color, width in ((RADIUS + 1, _HOT, 3), (RADIUS + 1, _CORE, 1)):
            x = centre + math.cos(angle) * radius
            y = centre + math.sin(angle) * radius
            shade = pygame.Color(color.r, color.g, color.b, round(alpha * (0.6 + 0.4 * u)))
            pygame.draw.circle(image, shade, (x, y), width / 2 + 0.5)
    return image


def arm(dx: float, dy: float) -> tuple[pygame.Surface, tuple[int, int]]:
    """The arm from the shoulder to a lantern `dx`, `dy` px away, and its top-left offset."""
    key = round(dx), round(dy)
    return _arm(*key), (min(key[0], 0), min(key[1], 0))


@functools.cache
def _arm(dx: int, dy: int) -> pygame.Surface:
    image = pygame.Surface((abs(dx) + 1, abs(dy) + 1), pygame.SRCALPHA)
    start = (0 if dx >= 0 else -dx, 0 if dy >= 0 else -dy)
    pygame.draw.line(image, ARM, start, (start[0] + dx, start[1] + dy))
    return image
