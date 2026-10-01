"""A 2D follow camera with deadzone, look-ahead, smoothing, bounds and shake.

The camera is updated once per simulation tick and interpolated for rendering, so motion stays
smooth at any frame rate. Positions are the centre of the view in world pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.mathx import clamp, damp
from emberwake.engine.render.shake import Shake, ShakeTuning

if TYPE_CHECKING:
    import pygame


@dataclass(slots=True)
class CameraTuning:
    """Follow behaviour. Lengths in px, rates per second.

    Attributes:
        deadzone: Width and height of the box the target can move in without moving the camera.
        smoothing: How fast the camera catches up with its goal.
        glide_smoothing: Catch-up rate while gliding into new bounds (room transitions).
        look_ahead: How far ahead of the target's facing the camera looks.
        look_ahead_rate: How fast the look-ahead swings when facing changes.
        vertical_bias: Added to the goal's y; negative shows more space above the target.
    """

    deadzone: tuple[float, float] = (24.0, 40.0)
    smoothing: float = 7.0
    glide_smoothing: float = 12.0
    look_ahead: float = 40.0
    look_ahead_rate: float = 2.5
    vertical_bias: float = -12.0
    shake: ShakeTuning = field(default_factory=ShakeTuning)


class Camera:
    """Follows a target inside optional bounds."""

    def __init__(self, view_size: tuple[int, int], tuning: CameraTuning | None = None) -> None:
        self.view_w, self.view_h = view_size
        self.tuning = tuning or CameraTuning()
        self.shake = Shake(self.tuning.shake)
        self.bounds: pygame.Rect | None = None
        self.x = self.y = 0.0
        self.previous = (0.0, 0.0)
        self.gliding = False
        self._focus = (0.0, 0.0)
        self._ahead = 0.0

    def retune(self, tuning: CameraTuning) -> None:
        """Swap tuning without moving the camera."""
        self.tuning = tuning
        self.shake.tuning = tuning.shake

    def snap(self, x: float, y: float) -> None:
        """Jump straight to look at (`x`, `y`), skipping smoothing and interpolation."""
        self._focus = (x, y)
        self._ahead = 0.0
        self.x, self.y = self._clamp(x, y + self.tuning.vertical_bias)
        self.previous = (self.x, self.y)

    def glide_to(self, bounds: pygame.Rect) -> None:
        """Switch to `bounds`, catching up faster until the view has settled inside them."""
        self.bounds = bounds
        self.gliding = True

    def update(self, target_x: float, target_y: float, facing: int, dt: float) -> None:
        """Advance one tick toward the target."""
        t = self.tuning
        self.previous = (self.x, self.y)
        fx, fy = self._focus
        half_w, half_h = t.deadzone[0] / 2, t.deadzone[1] / 2
        fx = clamp(fx, target_x - half_w, target_x + half_w)
        fy = clamp(fy, target_y - half_h, target_y + half_h)
        self._focus = (fx, fy)
        self._ahead = damp(self._ahead, facing * t.look_ahead, t.look_ahead_rate, dt)
        goal_x, goal_y = self._clamp(fx + self._ahead, fy + t.vertical_bias)
        rate = t.glide_smoothing if self.gliding else t.smoothing
        self.x = damp(self.x, goal_x, rate, dt)
        self.y = damp(self.y, goal_y, rate, dt)
        if self.gliding and abs(goal_x - self.x) < 1 and abs(goal_y - self.y) < 1:
            self.gliding = False
        self.shake.update(dt)

    def offset(self, alpha: float = 1.0) -> tuple[int, int]:
        """World position of the view's top-left pixel, interpolated and shaken."""
        px, py = self.previous
        sx, sy = self.shake.offset
        x = px + (self.x - px) * alpha + sx
        y = py + (self.y - py) * alpha + sy
        return round(x - self.view_w / 2), round(y - self.view_h / 2)

    def _clamp(self, x: float, y: float) -> tuple[float, float]:
        bounds = self.bounds
        if bounds is None:
            return x, y
        half_w, half_h = self.view_w / 2, self.view_h / 2
        if bounds.width <= self.view_w:
            x = bounds.centerx
        else:
            x = clamp(x, bounds.left + half_w, bounds.right - half_w)
        if bounds.height <= self.view_h:
            y = bounds.centery
        else:
            y = clamp(y, bounds.top + half_h, bounds.bottom - half_h)
        return x, y
