"""A pooled particle system driven by emitter specs from data.

Particles live in preallocated parallel lists and are removed by swapping with the last one, so
updating allocates nothing. When the pool is full, new particles are dropped, which caps the cost
of any frame.
"""

from __future__ import annotations

import math
import random
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True)
class EmitterSpec:
    """How one burst of particles behaves. Units: px, seconds, degrees (0 right, 90 down).

    Attributes:
        count: Particles per burst.
        speed: Launch speed range, px/s.
        angle: Launch direction range, degrees.
        life: Lifetime range, seconds.
        gravity: Downward acceleration, px/s².
        drag: Fraction of velocity lost per second.
        size: Square side in px.
        colors: Hex colors from young to old; a particle steps through them as it ages.
    """

    count: int = 16
    speed: tuple[float, float] = (40.0, 130.0)
    angle: tuple[float, float] = (0.0, 360.0)
    life: tuple[float, float] = (0.4, 0.8)
    gravity: float = 0.0
    drag: float = 0.0
    size: int = 2
    colors: list[str] = field(default_factory=lambda: ["#ffffff"])


def load_emitters(path: Path) -> dict[str, EmitterSpec]:
    """Parse a TOML file of named emitters. Raises `tomllib.TOMLDecodeError` or `SerdeError`."""
    return from_data(dict[str, EmitterSpec], tomllib.loads(path.read_text(encoding="utf-8")))


class ParticleSystem:
    """Up to `capacity` live particles. Seeded, so replays look the same."""

    def __init__(self, capacity: int = 512, seed: int = 0) -> None:
        self.capacity = capacity
        self.rng = random.Random(seed)
        self.count = 0
        self.dropped = 0
        """Particles refused for lack of room since the start."""
        self._x = [0.0] * capacity
        self._y = [0.0] * capacity
        self._vx = [0.0] * capacity
        self._vy = [0.0] * capacity
        self._age = [0.0] * capacity
        self._life = [0.0] * capacity
        self._spec: list[EmitterSpec] = [EmitterSpec()] * capacity
        self._ramps: dict[int, list[pygame.Color]] = {}

    def burst(self, spec: EmitterSpec, x: float, y: float) -> None:
        """Launch `spec.count` particles from `(x, y)` in world px."""
        rng = self.rng
        for _ in range(spec.count):
            if self.count == self.capacity:
                self.dropped += 1
                continue
            i = self.count
            angle = math.radians(rng.uniform(*spec.angle))
            speed = rng.uniform(*spec.speed)
            self._x[i], self._y[i] = x, y
            self._vx[i], self._vy[i] = math.cos(angle) * speed, math.sin(angle) * speed
            self._age[i], self._life[i] = 0.0, rng.uniform(*spec.life)
            self._spec[i] = spec
            self.count += 1

    def update(self, dt: float) -> None:
        """Move and age every particle, then retire the ones out of life."""
        i = 0
        while i < self.count:
            spec = self._spec[i]
            self._age[i] += dt
            if self._age[i] >= self._life[i]:
                self._remove(i)
                continue
            damping = max(1.0 - spec.drag * dt, 0.0)
            self._vx[i] *= damping
            self._vy[i] = self._vy[i] * damping + spec.gravity * dt
            self._x[i] += self._vx[i] * dt
            self._y[i] += self._vy[i] * dt
            i += 1

    def draw(self, canvas: pygame.Surface, offset: tuple[int, int]) -> None:
        """Draw every particle; `offset` is the camera's world position."""
        ox, oy = offset
        for i in range(self.count):
            spec = self._spec[i]
            ramp = self._ramp(spec)
            color = ramp[min(int(self._age[i] / self._life[i] * len(ramp)), len(ramp) - 1)]
            x, y = round(self._x[i]) - ox, round(self._y[i]) - oy
            canvas.fill(color, (x, y, spec.size, spec.size))

    def clear(self) -> None:
        """Remove every particle."""
        self.count = 0

    def _remove(self, i: int) -> None:
        last = self.count - 1
        if i != last:
            self._x[i], self._y[i] = self._x[last], self._y[last]
            self._vx[i], self._vy[i] = self._vx[last], self._vy[last]
            self._age[i], self._life[i] = self._age[last], self._life[last]
            self._spec[i] = self._spec[last]
        self.count = last

    def _ramp(self, spec: EmitterSpec) -> list[pygame.Color]:
        key = id(spec)
        if key not in self._ramps:
            self._ramps[key] = [pygame.Color(color) for color in spec.colors]
        return self._ramps[key]
