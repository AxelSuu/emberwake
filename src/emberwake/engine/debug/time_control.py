"""Pause, single-step and slow motion for debugging the simulation."""

from __future__ import annotations


class TimeControl:
    """Decides whether each simulation tick should run.

    Slow motion runs one of every `slow_factor` ticks, so the simulation itself stays exactly
    the same, just stretched in time.
    """

    def __init__(self, slow_factor: int = 4) -> None:
        self.paused = False
        self.slow = False
        self.slow_factor = slow_factor
        self._step = False
        self._counter = 0

    def toggle_pause(self) -> None:
        """Pause or resume."""
        self.paused = not self.paused

    def step(self) -> None:
        """While paused, run exactly one more tick."""
        self._step = True

    def toggle_slow(self) -> None:
        """Switch slow motion on or off."""
        self.slow = not self.slow

    def should_tick(self) -> bool:
        """Call once per tick; returns whether the simulation should advance."""
        if self.paused:
            stepping, self._step = self._step, False
            return stepping
        if not self.slow:
            return True
        self._counter += 1
        return self._counter % self.slow_factor == 0
