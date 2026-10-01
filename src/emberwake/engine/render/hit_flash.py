"""A white hit flash: a timer, and a way to paint a sprite's silhouette white."""

from __future__ import annotations

import pygame

STEPS = 8


class HitFlash:
    """Counts down a flash. `amount` is 1 at the start and falls to 0."""

    def __init__(self, duration: float = 0.12) -> None:
        self.duration = duration
        self.left = 0.0
        self.muted = False
        """Reduce-flashes setting: never flash."""

    def start(self) -> None:
        """Begin (or restart) the flash."""
        if not self.muted:
            self.left = self.duration

    def update(self, dt: float) -> None:
        """Advance the countdown."""
        self.left = max(self.left - dt, 0.0)

    @property
    def amount(self) -> float:
        """0 to 1: how white the sprite should be right now."""
        return self.left / self.duration if self.duration > 0 else 0.0


def flashed(image: pygame.Surface, amount: float) -> pygame.Surface:
    """A copy of `image` with its opaque pixels blended toward white by `amount` (0 to 1).

    `amount` is quantized to a few steps. At 0 the image itself is returned.
    """
    step = round(max(0.0, min(amount, 1.0)) * STEPS)
    if step == 0:
        return image
    white = pygame.mask.from_surface(image).to_surface(
        setcolor=(255, 255, 255, round(255 * step / STEPS)), unsetcolor=(0, 0, 0, 0)
    )
    out = image.copy()
    out.blit(white, (0, 0))
    return out
