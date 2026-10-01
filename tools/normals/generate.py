"""Normal maps from an albedo's alpha bevel and an optional height layer.

Conventions: tangent-space, +x right, +y up (green is up), flat is (128, 128, 255).
Sprites named ``name.png`` get ``name_n.png``; a ``name_h.png`` greyscale layer adds height.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from pathlib import Path

HEIGHT_SUFFIX = "_h"
NORMAL_SUFFIX = "_n"
EMISSIVE_SUFFIX = "_e"
FLAT = (128, 128, 255, 255)


def bevel(alpha: list[list[bool]], radius: int) -> list[list[float]]:
    """Height 0..1 rising from the silhouette edge to `radius` pixels inside (chamfer distance)."""
    h, w = len(alpha), len(alpha[0]) if alpha else 0
    far = radius + 1
    dist = [[0 if alpha[y][x] is False else far for x in range(w)] for y in range(h)]
    for y in range(h):
        for x in range(w):
            if not dist[y][x]:
                continue
            best = dist[y][x]
            for dx, dy in ((-1, 0), (0, -1), (-1, -1), (1, -1)):
                nx, ny = x + dx, y + dy
                outside = not (0 <= nx < w and 0 <= ny < h)
                best = min(best, 1 if outside else dist[ny][nx] + 1)
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                best = 1
            dist[y][x] = best
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            best = dist[y][x]
            if not best:
                continue
            for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    best = min(best, dist[ny][nx] + 1)
            dist[y][x] = best
    return [[min(d, radius) / radius for d in row] for row in dist]


def heights(
    albedo: pygame.Surface, height: pygame.Surface | None, radius: int, depth: float
) -> list[list[float]]:
    """Bevel height plus `depth` times the height layer's luma, where the sprite is opaque."""
    w, h = albedo.get_size()
    alpha = [[albedo.get_at((x, y)).a > 0 for x in range(w)] for y in range(h)]
    field = bevel(alpha, radius)
    if height is not None:
        for y in range(h):
            for x in range(w):
                r, g, b, _ = height.get_at((x, y))
                field[y][x] += depth * (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return field


def normals(field: list[list[float]], alpha: pygame.Surface, strength: float) -> pygame.Surface:
    """Shade a height field with central differences; transparent pixels stay transparent."""
    h = len(field)
    w = len(field[0]) if h else 0
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))

    def at(x: int, y: int) -> float:
        return field[min(max(y, 0), h - 1)][min(max(x, 0), w - 1)]

    for y in range(h):
        for x in range(w):
            if alpha.get_at((x, y)).a == 0:
                continue
            dx = (at(x + 1, y) - at(x - 1, y)) * 0.5 * strength
            dy = (at(x, y + 1) - at(x, y - 1)) * 0.5 * strength
            nx, ny, nz = -dx, dy, 1.0
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            out.set_at(
                (x, y),
                (*(round((c / length * 0.5 + 0.5) * 255) for c in (nx, ny, nz)), 255),
            )
    return out


def load(path: Path) -> pygame.Surface:
    image = pygame.image.load(path)
    surface = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    surface.blit(image, (0, 0))
    return surface


def is_derived(path: Path) -> bool:
    return path.stem.endswith((HEIGHT_SUFFIX, NORMAL_SUFFIX, EMISSIVE_SUFFIX))


def generate_file(
    source: Path, *, radius: int = 2, strength: float = 2.0, depth: float = 1.0
) -> Path:
    """Write ``<name>_n.png`` beside `source`, using ``<name>_h.png`` when present."""
    albedo = load(source)
    layer = source.with_name(source.stem + HEIGHT_SUFFIX + ".png")
    height = load(layer) if layer.exists() else None
    if height is not None and height.get_size() != albedo.get_size():
        raise ValueError(f"{layer} is {height.get_size()}, expected {albedo.get_size()}")
    out = source.with_name(source.stem + NORMAL_SUFFIX + ".png")
    pygame.image.save(normals(heights(albedo, height, radius, depth), albedo, strength), out)
    return out


def generate(root: Path, **options: float) -> list[Path]:
    """Generate normals for every albedo PNG under `root`."""
    sources = sorted(p for p in root.glob("**/*.png") if not is_derived(p))
    return [generate_file(p, **options) for p in sources]  # ty: ignore[invalid-argument-type]
