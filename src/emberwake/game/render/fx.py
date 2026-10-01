"""Placeholder effects until the particle system and post effects (M3): sparks and a flash."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from emberwake.game import palette

GRAVITY = 220.0


@dataclass(slots=True)
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: float


class Sparks:
    """Embers flung out in a burst, falling and fading. Seeded, so replays look the same."""

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.items: list[Spark] = []

    def burst(self, x: float, y: float, count: int = 24) -> None:
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(40, 130)
            life = self.rng.uniform(0.35, 0.8)
            self.items.append(Spark(x, y, math.cos(angle) * speed, math.sin(angle) * speed, life))

    def update(self, dt: float) -> None:
        for spark in self.items:
            spark.vy += GRAVITY * dt
            spark.x += spark.vx * dt
            spark.y += spark.vy * dt
            spark.life -= dt
        self.items = [spark for spark in self.items if spark.life > 0]

    def draw(self, canvas: pygame.Surface, offset: tuple[int, int]) -> None:
        for spark in self.items:
            color = palette.EMBER_CORE if spark.life > 0.4 else palette.EMBER_WARM
            canvas.fill(color, (round(spark.x) - offset[0], round(spark.y) - offset[1], 2, 2))


class Flash:
    """A full-screen flash that fades out."""

    def __init__(self, color: str = palette.MIST, strength: int = 150) -> None:
        self.color = color
        self.strength = strength
        self.left = self.duration = 0.0
        self._surface: pygame.Surface | None = None

    def start(self, duration: float) -> None:
        self.left = self.duration = duration

    def update(self, dt: float) -> None:
        self.left = max(self.left - dt, 0.0)

    def draw(self, canvas: pygame.Surface) -> None:
        if self.left <= 0:
            return
        if self._surface is None or self._surface.get_size() != canvas.get_size():
            self._surface = pygame.Surface(canvas.get_size())
            self._surface.fill(self.color)
        self._surface.set_alpha(round(self.strength * self.left / self.duration))
        canvas.blit(self._surface, (0, 0))
