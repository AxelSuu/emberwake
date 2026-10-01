"""Room backdrops: presets from content/backdrops.toml drawn as placeholder parallax layers.

Far layers (factor up to 1) draw behind the world, blurred once for depth; near layers (factor
above 1) pass in front of it, darkened. Switching presets cross-fades, and a room with a lit
beacon warms up, a preview of the colour grade in M3.
"""

from __future__ import annotations

import random
import tomllib
import zlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import pygame

from emberwake.engine.core.mathx import approach
from emberwake.engine.core.serde import from_data
from emberwake.engine.render.parallax import ParallaxLayer, wrap_blur
from emberwake.game import palette

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

FADE = 0.5
"""Seconds a cross-fade between presets takes."""
WARM = (46, 18, 2)
"""Light added to a warm backdrop at full warmth."""
WARM_RATE = 1.2
NEAR_SHADE = (120, 110, 130)


@dataclass(slots=True)
class LayerSpec:
    kind: Literal["skyline", "pillars", "mist"]
    factor: float
    color: str
    top: int = 120
    height: int = 260
    blur: int = 0
    width: tuple[int, int] = (14, 44)
    """Range of shape widths (skyline, pillars)."""
    gap: tuple[int, int] = (2, 14)
    """Range of gaps between shapes (skyline, pillars)."""


@dataclass(slots=True)
class BackdropSpec:
    sky: tuple[str, str] = (palette.INK, palette.PLUM)
    layers: list[LayerSpec] = field(default_factory=list)


def load_backdrops(path: Path) -> dict[str, BackdropSpec]:
    return from_data(dict[str, BackdropSpec], tomllib.loads(path.read_text(encoding="utf-8")))


class Backdrop:
    """A preset rendered once at a canvas size."""

    def __init__(self, name: str, spec: BackdropSpec, size: tuple[int, int]) -> None:
        self.sky = _gradient(size, pygame.Color(spec.sky[0]), pygame.Color(spec.sky[1]))
        self.far: list[ParallaxLayer] = []
        self.near: list[ParallaxLayer] = []
        for index, layer in enumerate(spec.layers):
            rng = random.Random(zlib.crc32(f"{name}:{index}".encode()))
            image = GENERATORS[layer.kind]((size[0] * 2, layer.height), rng, layer)
            if layer.blur:
                image = wrap_blur(image, layer.blur)
            if layer.factor > 1:
                image.fill(NEAR_SHADE, special_flags=pygame.BLEND_RGB_MULT)
            target = self.near if layer.factor > 1 else self.far
            target.append(ParallaxLayer(image, layer.factor, layer.top))

    def draw_far(self, canvas: pygame.Surface, offset: tuple[int, int], room_top: int) -> None:
        canvas.blit(self.sky, (0, 0))
        for layer in self.far:
            layer.draw(canvas, offset, room_top)

    def draw_near(self, canvas: pygame.Surface, offset: tuple[int, int], room_top: int) -> None:
        for layer in self.near:
            layer.draw(canvas, offset, room_top)


class Backdrops:
    """The active room's backdrop: cross-fades between presets and warms when asked."""

    def __init__(self, specs: dict[str, BackdropSpec], size: tuple[int, int]) -> None:
        self.specs = specs
        self.size = size
        self.current: str | None = None
        self.previous: str | None = None
        self.fade = 0.0
        self.warmth = 0.0
        self._cache: dict[str, Backdrop] = {}
        self._buffer = pygame.Surface(size)

    def prepare(self, names: Iterable[str | None]) -> None:
        """Build presets now (tens of ms each), so showing them later never stalls a frame."""
        for name in names:
            self.get(name)

    def get(self, name: str | None) -> Backdrop | None:
        if name is None or name not in self.specs:
            return None
        if name not in self._cache:
            self._cache[name] = Backdrop(name, self.specs[name], self.size)
        return self._cache[name]

    def show(self, name: str | None, *, instantly: bool = False) -> None:
        """Make `name` the backdrop, cross-fading from the current one."""
        if name == self.current:
            return
        self.previous, self.current = self.current, name
        self.fade = 0.0 if instantly else FADE

    def update(self, warm: bool, dt: float) -> None:
        self.fade = max(self.fade - dt, 0.0)
        self.warmth = approach(self.warmth, 1.0 if warm else 0.0, WARM_RATE * dt)

    def draw_far(self, canvas: pygame.Surface, offset: tuple[int, int], room_top: int) -> None:
        current = self.get(self.current)
        if current is None:
            canvas.fill(palette.INK)
        else:
            current.draw_far(canvas, offset, room_top)
        previous = self.get(self.previous)
        if self.fade > 0 and previous is not None:
            previous.draw_far(self._buffer, offset, room_top)
            self._buffer.set_alpha(round(255 * self.fade / FADE))
            canvas.blit(self._buffer, (0, 0))
        if self.warmth > 0:
            canvas.fill([round(c * self.warmth) for c in WARM], special_flags=pygame.BLEND_RGB_ADD)

    def draw_near(self, canvas: pygame.Surface, offset: tuple[int, int], room_top: int) -> None:
        current = self.get(self.current)
        if current is not None:
            current.draw_near(canvas, offset, room_top)


def _gradient(size: tuple[int, int], top: pygame.Color, bottom: pygame.Color) -> pygame.Surface:
    surface = pygame.Surface(size)
    width, height = size
    for y in range(height):
        pygame.draw.line(surface, top.lerp(bottom, y / max(height - 1, 1)), (0, y), (width, y))
    return surface


def _skyline(size: tuple[int, int], rng: random.Random, spec: LayerSpec) -> pygame.Surface:
    width, height = size
    color = pygame.Color(spec.color)
    image = pygame.Surface(size, pygame.SRCALPHA)
    x = 0
    while x < width:
        w = rng.randint(*spec.width)
        top = rng.randint(0, height // 2)
        image.fill(color, (x, top, min(w, width - x), height - top))
        if rng.random() < 0.3:
            image.fill(color, (x + w // 2 - 1, max(top - rng.randint(6, 18), 0), 2, 18))
        x += w + rng.randint(*spec.gap)
    return image


def _pillars(size: tuple[int, int], rng: random.Random, spec: LayerSpec) -> pygame.Surface:
    width, height = size
    color = pygame.Color(spec.color)
    image = pygame.Surface(size, pygame.SRCALPHA)
    x = rng.randint(0, spec.gap[0])
    while x < width - 6:
        w = min(rng.randint(*spec.width), width - 3 - x)
        image.fill(color, (x, 0, w, height))
        image.fill(color, (x - 3, height - 10, w + 6, 10))
        image.fill(color, (x - 3, 0, w + 6, 8))
        x += w + rng.randint(*spec.gap)
    return image


def _mist(size: tuple[int, int], rng: random.Random, spec: LayerSpec) -> pygame.Surface:
    width, height = size
    color = pygame.Color(spec.color)
    image = pygame.Surface(size, pygame.SRCALPHA)
    for _ in range(14):
        band = pygame.Color(color)
        band.a = rng.randint(30, 80)
        w, h = rng.randint(160, 420), rng.randint(10, 28)
        x, y = rng.randint(0, width), rng.randint(0, height - h)
        for dx in (-width, 0):
            pygame.draw.ellipse(image, band, (x + dx, y, w, h))
    image.fill(color, (0, height * 3 // 4, width, height - height * 3 // 4))
    return image


GENERATORS = {"skyline": _skyline, "pillars": _pillars, "mist": _mist}
