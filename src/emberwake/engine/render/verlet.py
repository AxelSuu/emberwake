"""Verlet chains for secondary motion: scarves, capes, chains, hanging lamps.

Purely visual: a chain follows its anchor with inertia and gravity and never touches the
simulation, so it may run on the frame's `dt`.

Example:
    >>> chain = Chain((0.0, 0.0), links=4, length=3.0)
    >>> for _ in range(60):
    ...     chain.update((10.0, 0.0), 1 / 60)
    >>> chain.points[0]
    (10.0, 0.0)
    >>> chain.points[-1][1] > 5
    True
"""

from __future__ import annotations

import math


class Chain:
    """Points joined by links of fixed `length`; the first follows an anchor.

    Args:
        anchor: Where the chain starts, px.
        links: Number of links (points minus one).
        length: Length of each link, px.
        gravity: Downward pull, px/s².
        damping: Share of velocity kept per 1/60 s (1 keeps it all).
        iterations: Constraint passes per update; more is stiffer.
    """

    def __init__(
        self,
        anchor: tuple[float, float],
        links: int = 5,
        length: float = 3.0,
        *,
        gravity: float = 400.0,
        damping: float = 0.9,
        iterations: int = 4,
    ) -> None:
        x, y = anchor
        self.points = [(x, y + i * length) for i in range(links + 1)]
        self._previous = list(self.points)
        self.length = length
        self.gravity = gravity
        self.damping = damping
        self.iterations = iterations
        self.wind = 0.0
        """Sideways push, px/s², for drafts and the wake of moving."""

    def reset(self, anchor: tuple[float, float]) -> None:
        """Hang straight down from `anchor`, at rest (after a teleport)."""
        x, y = anchor
        self.points = [(x, y + i * self.length) for i in range(len(self.points))]
        self._previous = list(self.points)

    def update(self, anchor: tuple[float, float], dt: float) -> None:
        """Pin the first point to `anchor`, integrate the rest and keep the link lengths."""
        if dt <= 0:
            return
        keep = self.damping ** (dt * 60)
        ax, ay = self.wind * dt * dt, self.gravity * dt * dt
        moved = [anchor]
        for (x, y), (px, py) in zip(self.points[1:], self._previous[1:], strict=True):
            moved.append((x + (x - px) * keep + ax, y + (y - py) * keep + ay))
        self._previous = [anchor, *self.points[1:]]
        for _ in range(self.iterations):
            moved = self._constrain(moved)
        self.points = moved

    def _constrain(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        out = [points[0]]
        for x, y in points[1:]:
            px, py = out[-1]
            dx, dy = x - px, y - py
            distance = math.hypot(dx, dy) or 1e-6
            scale = self.length / distance
            out.append((px + dx * scale, py + dy * scale))
        return out
