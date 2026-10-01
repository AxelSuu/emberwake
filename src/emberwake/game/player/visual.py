"""Purely visual player state: squash and stretch. Never affects movement."""

from __future__ import annotations

from dataclasses import dataclass

from emberwake.engine.core.mathx import damp


@dataclass(slots=True)
class PlayerVisual:
    scale_x: float = 1.0
    scale_y: float = 1.0

    def squash(self, amount: float) -> None:
        self.scale_x, self.scale_y = 1 + amount, 1 - amount

    def stretch(self, amount: float) -> None:
        self.scale_x, self.scale_y = 1 - amount, 1 + amount

    def update(self, recovery: float, dt: float) -> None:
        self.scale_x = damp(self.scale_x, 1.0, recovery, dt)
        self.scale_y = damp(self.scale_y, 1.0, recovery, dt)
