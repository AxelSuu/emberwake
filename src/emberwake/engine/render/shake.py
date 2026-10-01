"""Trauma-based screen shake (Squirrel Eiserloh, "Juicing Your Cameras With Math").

Events add trauma in ``[0, 1]``; the offset grows with trauma squared, so small hits barely
move the screen while big ones really kick, and trauma decays linearly over time.
"""

from __future__ import annotations

from dataclasses import dataclass

from emberwake.engine.core.noise import ValueNoise


@dataclass(slots=True)
class ShakeTuning:
    """Shake behaviour. Lengths in px, rates per second."""

    max_offset: float = 10.0
    frequency: float = 22.0
    decay: float = 1.6


class Shake:
    """Accumulates trauma and turns it into a smooth, deterministic offset.

    Attributes:
        intensity: Player preference multiplier (0 disables shaking).
    """

    def __init__(self, tuning: ShakeTuning | None = None, seed: int = 0) -> None:
        self.tuning = tuning or ShakeTuning()
        self.intensity = 1.0
        self.trauma = 0.0
        self._time = 0.0
        self._noise_x = ValueNoise(seed)
        self._noise_y = ValueNoise(seed + 1)

    def add(self, trauma: float) -> None:
        """Add trauma, saturating at 1."""
        self.trauma = min(self.trauma + trauma, 1.0)

    def update(self, dt: float) -> None:
        """Advance time and decay trauma."""
        self._time += dt
        self.trauma = max(self.trauma - self.tuning.decay * dt, 0.0)

    @property
    def offset(self) -> tuple[float, float]:
        """Current offset in px."""
        if self.trauma == 0 or self.intensity == 0:
            return 0.0, 0.0
        amount = self.tuning.max_offset * self.intensity * self.trauma**2
        t = self._time * self.tuning.frequency
        return amount * self._noise_x(t), amount * self._noise_y(t)
