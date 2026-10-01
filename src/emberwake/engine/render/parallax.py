"""Parallax layers: images that scroll at a fraction of the camera and wrap horizontally."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from emberwake.engine.core.mathx import clamp


@dataclass(slots=True)
class ParallaxLayer:
    """One horizontally tiling image.

    Attributes:
        image: The tile; it repeats left and right.
        factor: Scroll speed relative to the world: 0 is fixed to the screen, 1 moves with the
            world, above 1 is a foreground layer passing in front of it.
        top: Screen y of the image's top when the camera is at the top of the room. Scrolling
            down raises it, never so far that its bottom edge leaves the screen bottom.
    """

    image: pygame.Surface
    factor: float
    top: int

    def draw(self, target: pygame.Surface, offset: tuple[float, float], room_top: float) -> None:
        """Draw for a camera whose view's top-left is at world `offset`, in a room at `room_top`."""
        width, height = self.image.get_size()
        screen_w, screen_h = target.get_size()
        y = self.top - (offset[1] - room_top) * self.factor
        y = round(clamp(y, min(screen_h - height, self.top), self.top))
        x = -round(offset[0] * self.factor) % width - width
        blits = []
        while x < screen_w:
            blits.append((self.image, (x, y)))
            x += width
        target.fblits(blits)


def wrap_blur(image: pygame.Surface, radius: int) -> pygame.Surface:
    """Blur a horizontally tiling image without seams at its left and right edges.

    The blur runs at half resolution with half the radius and is scaled back up, which looks
    the same on soft backgrounds and is several times cheaper.
    """
    width, height = image.get_size()
    pad = radius * 3
    strip = pygame.Surface((width + 2 * pad, height), pygame.SRCALPHA)
    for x in (pad - width, pad, pad + width):
        strip.blit(image, (x, 0))
    half = pygame.transform.smoothscale(strip, (strip.get_width() // 2, height // 2))
    half = pygame.transform.gaussian_blur(half, max(1, round(radius / 2)))
    blurred = pygame.transform.smoothscale(half, strip.get_size())
    return blurred.subsurface((pad, 0, width, height)).copy()
