"""Fixed-timestep accumulator.

The simulation always advances in identical steps so gameplay is deterministic and replayable,
while rendering runs at whatever rate the display allows. `alpha` tells the renderer how far
it is between the last two simulation states, for interpolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FixedStep:
    """Converts variable frame times into a whole number of fixed simulation steps.

    Attributes:
        step: Simulation step length in seconds.
        max_frame: Longest frame time honoured; longer frames (debugger pauses, window drags)
            are clamped to avoid a spiral of death.
    """

    step: float = 1 / 60
    max_frame: float = 0.25
    _accumulator: float = field(default=0.0, init=False)

    def advance(self, frame_time: float) -> int:
        """Add `frame_time` seconds and return how many steps should run now."""
        self._accumulator += min(max(frame_time, 0.0), self.max_frame)
        # Epsilon absorbs float error so exactly-one-step frames never round down to zero.
        steps = int(self._accumulator / self.step + 1e-9)
        self._accumulator = max(self._accumulator - steps * self.step, 0.0)
        return steps

    @property
    def alpha(self) -> float:
        """Fraction of a step left in the accumulator, in ``[0, 1)``."""
        return self._accumulator / self.step
