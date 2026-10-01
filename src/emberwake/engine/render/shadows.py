"""Soft 2D shadows for the software backend: ray-cast visibility from a light, blurred."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable

    type Occluded = Callable[[float, float], bool]
    """Whether the screen px point is inside something that blocks light."""

RAYS = 48
STEP = 3.0
SOFTNESS = 1


def visible_outline(
    occluded: Occluded, x: float, y: float, radius: int, rays: int = RAYS
) -> list[tuple[float, float]] | None:
    """Where each ray from `(x, y)` ends: at the first blocked point, or at `radius`.

    Returns None when nothing within reach blocks the light, or the light sits inside a block.
    """
    if occluded(x, y):
        return None
    points: list[tuple[float, float]] = []
    blocked = False
    for i in range(rays):
        angle = math.tau * i / rays
        dx, dy = math.cos(angle), math.sin(angle)
        distance = 0.0
        while distance < radius:
            distance = min(distance + STEP, radius)
            if occluded(x + dx * distance, y + dy * distance):
                blocked = True
                distance -= STEP / 2
                break
        points.append((x + dx * distance, y + dy * distance))
    return points if blocked else None


def shadow_mask(
    occluded: Occluded, x: float, y: float, radius: int, like: pygame.Surface
) -> pygame.Surface | None:
    """A `2 * radius` square, white where the light at its centre reaches and black in shadow.

    Drawn at half resolution and scaled up, which also softens the edges. None means no shadow.
    """
    outline = visible_outline(occluded, x, y, radius)
    if outline is None:
        return None
    half = radius
    small = pygame.Surface((half, half), 0, like)
    small.fill((0, 0, 0))
    points = [((px - x) / 2 + half / 2, (py - y) / 2 + half / 2) for px, py in outline]
    pygame.draw.polygon(small, (255, 255, 255), points)
    small = pygame.transform.gaussian_blur(small, SOFTNESS)
    return pygame.transform.smoothscale(small, (radius * 2, radius * 2))
