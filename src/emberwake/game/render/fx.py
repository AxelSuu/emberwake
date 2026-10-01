"""Placeholder effects until the post effects (M3): a flash."""

from __future__ import annotations

import pygame

from emberwake.game import palette


class Flash:
    """A full-screen flash that fades out."""

    def __init__(self, color: str = palette.MIST, strength: int = 150) -> None:
        self.color = color
        self.strength = strength
        self.left = self.duration = 0.0
        self.muted = False
        """Reduce-flashes setting: never show."""
        self._surface: pygame.Surface | None = None

    def start(self, duration: float) -> None:
        if self.muted:
            return
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
