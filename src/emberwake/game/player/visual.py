"""Purely visual player state: squash and stretch, the swinging lantern, the run cycle, breath.

Nothing here affects movement. `animate` runs once per tick from the motor's state and returns
the moments other effects hang on (footsteps for dust and sound, wall-slide scrapes).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.mathx import clamp, damp
from emberwake.game.player.controller import PlayerState

if TYPE_CHECKING:
    from emberwake.game.player.controller import Motor
    from emberwake.game.player.kindle import Kindle
    from emberwake.game.player.swing import Swing

HANDLE = 6.0
"""Length of the lantern's pendulum, px; shorter swings faster."""
GRAVITY = 600.0
SWAY = 0.5
"""How much the lantern lags behind changes of speed."""
SWAY_DAMPING = 0.9
"""Share of the swing kept per 1/60 s."""
MAX_ANGLE = 1.1
STRIDE = 0.085
"""Run-cycle radians per px travelled; a footstep every half turn."""
BREATH = 0.03
BREATH_RATE = 2.2
SCRAPE_EVERY = 0.12
"""Seconds between wall-slide scrapes."""


@dataclass(slots=True)
class PlayerVisual:
    scale_x: float = 1.0
    scale_y: float = 1.0
    lantern_angle: float = 0.0
    """Radians from hanging straight down; positive swings toward +x."""
    lantern_spin: float = 0.0
    stride: float = 0.0
    """Run-cycle phase, radians."""
    bob: int = 0
    """Px the body is lifted this tick by the run cycle."""
    breath: float = 0.0
    """Extra height from breathing, as a share of the sprite."""
    time: float = 0.0
    scrape: float = 0.0
    _last_vx: float = field(default=0.0, repr=False)

    def squash(self, amount: float) -> None:
        self.scale_x, self.scale_y = 1 + amount, 1 - amount

    def stretch(self, amount: float) -> None:
        self.scale_x, self.scale_y = 1 - amount, 1 + amount

    def update(self, recovery: float, dt: float) -> None:
        self.scale_x = damp(self.scale_x, 1.0, recovery, dt)
        self.scale_y = damp(self.scale_y, 1.0, recovery, dt)

    def animate(self, motor: Motor, dt: float) -> list[str]:
        """Advance the lantern, run cycle and breath one tick; returns ``step``/``scrape``."""
        events: list[str] = []
        self.time += dt
        accel = (motor.vx - self._last_vx) / dt if dt > 0 else 0.0
        self._last_vx = motor.vx
        a = self.lantern_angle
        push = -accel * SWAY * math.cos(a) - GRAVITY * math.sin(a)
        self.lantern_spin = (self.lantern_spin + push / HANDLE * dt) * SWAY_DAMPING ** (dt * 60)
        self.lantern_angle = clamp(a + self.lantern_spin * dt, -MAX_ANGLE, MAX_ANGLE)
        running = motor.grounded and abs(motor.vx) > 30 and not motor.dead
        if running:
            before = math.floor(self.stride / math.pi)
            self.stride += abs(motor.vx) * dt * STRIDE
            if math.floor(self.stride / math.pi) != before:
                events.append("step")
            self.bob = round(abs(math.sin(self.stride)))
        else:
            self.stride, self.bob = 0.0, 0
        idle = motor.grounded and abs(motor.vx) < 10
        self.breath = math.sin(self.time * BREATH_RATE) * BREATH if idle else 0.0
        if motor.state is PlayerState.WALL_SLIDE:
            self.scrape += dt
            if self.scrape >= SCRAPE_EVERY:
                self.scrape = 0.0
                events.append("scrape")
        else:
            self.scrape = 0.0
        return events


def anim_state(motor: Motor, swing: Swing | None = None, kindle: Kindle | None = None) -> str:
    """The clip the player shows now; finished sheets are looked up as ``player_<state>``.

    One of ``idle``, ``run``, ``jump``, ``fall``, ``wall``, ``dash``, ``swing_forward``,
    ``swing_up``, ``swing_down``, ``kindle`` or ``death``.
    """
    if motor.dead:
        state = "death"
    elif swing is not None and swing.tick:
        state = f"swing_{swing.direction.value}"
    elif motor.state is PlayerState.DASH:
        state = "dash"
    elif motor.state is PlayerState.WALL_SLIDE:
        state = "wall"
    elif not motor.grounded:
        state = "jump" if motor.vy < 0 else "fall"
    elif kindle is not None and kindle.ticks:
        state = "kindle"
    else:
        state = "run" if abs(motor.vx) > 10 else "idle"
    return state
