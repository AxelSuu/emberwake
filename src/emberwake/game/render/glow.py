"""The pixels of a sprite that give off light, drawn again after the lighting (Layer.GLOW)."""

from __future__ import annotations

import pygame

from emberwake.game import palette

_EMISSIVE = [pygame.Color(color) for color in palette.EMISSIVE]
_EXACT = (1, 1, 1, 255)


def glow_of(image: pygame.Surface) -> pygame.Surface | None:
    """A copy of `image` holding only its emissive pixels, or None if it has none."""
    mask = pygame.mask.Mask(image.get_size())
    for color in _EMISSIVE:
        mask.draw(pygame.mask.from_threshold(image, color, _EXACT), (0, 0))
    if mask.count() == 0:
        return None
    return mask.to_surface(setsurface=image, unsetcolor=(0, 0, 0, 0))


class Glows:
    """`glow_of` with a cache keyed by the source surface."""

    def __init__(self) -> None:
        self._cache: dict[pygame.Surface, pygame.Surface | None] = {}

    def __call__(self, image: pygame.Surface) -> pygame.Surface | None:
        if image not in self._cache:
            self._cache[image] = glow_of(image)
        return self._cache[image]

    def clear(self) -> None:
        self._cache.clear()
