"""Software post effects on the finished canvas: grade, bloom, vignette and CRT scanlines.

Each effect is a few full-canvas blits, cheap at pixel-art sizes, and runs only when its `Flag`
is set. The GL backend does the same in shaders.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from emberwake.engine.core.mathx import clamp
from emberwake.engine.render.frame import Flag

BLOOM_THRESHOLD = 150
BLOOM_SCALE = 4
BLOOM_BLUR = 2
BLOOM_STRENGTH = 0.6
VIGNETTE_STRENGTH = 0.55
SCANLINE_SHADE = 200


@dataclass(frozen=True, slots=True)
class Grade:
    """A colour grade.

    Saturation is set first (1 keeps it, 0 is grey), then the canvas is scaled by `multiply` out
    of 255 and `add` is added.
    """

    multiply: tuple[int, int, int] = (255, 255, 255)
    add: tuple[int, int, int] = (0, 0, 0)
    saturation: float = 1.0

    def lerp(self, other: Grade, t: float) -> Grade:
        """Blend toward `other`; `t` 0 is this grade, 1 is `other`."""
        t = clamp(t, 0.0, 1.0)

        def mix(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[int, int, int]:
            r, g, bl = (round(x + (y - x) * t) for x, y in zip(a, b, strict=True))
            return r, g, bl

        return Grade(
            mix(self.multiply, other.multiply),
            mix(self.add, other.add),
            self.saturation + (other.saturation - self.saturation) * t,
        )

    @property
    def neutral(self) -> bool:
        """Whether applying it would change nothing."""
        return self == Grade()


class PostChain:
    """Applies the enabled effects to a canvas of a fixed size."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size
        self._vignette = self._build_vignette(size)
        self._scanlines = self._build_scanlines(size)
        self._small = (max(size[0] // BLOOM_SCALE, 1), max(size[1] // BLOOM_SCALE, 1))
        self._bright = pygame.Surface(size)

    def apply(self, canvas: pygame.Surface, flags: Flag, grade: Grade | None = None) -> None:
        """Run the effects `flags` ask for, in the order bloom, grade, vignette, CRT."""
        if Flag.BLOOM in flags:
            self._bloom(canvas)
        if Flag.GRADING in flags and grade is not None and not grade.neutral:
            self._grade(canvas, grade)
        if Flag.VIGNETTE in flags:
            canvas.blit(self._vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if Flag.CRT in flags:
            canvas.blit(self._scanlines, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def _bloom(self, canvas: pygame.Surface) -> None:
        bright = self._bright
        bright.blit(canvas, (0, 0))
        bright.fill((BLOOM_THRESHOLD,) * 3, special_flags=pygame.BLEND_RGB_SUB)
        small = pygame.transform.smoothscale(bright, self._small)
        small = pygame.transform.gaussian_blur(small, BLOOM_BLUR)
        glow = pygame.transform.smoothscale(small, self.size)
        scale = round(255 * BLOOM_STRENGTH * 255 / (255 - BLOOM_THRESHOLD))
        glow.fill((min(scale, 255),) * 3, special_flags=pygame.BLEND_RGB_MULT)
        canvas.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    @staticmethod
    def _grade(canvas: pygame.Surface, grade: Grade) -> None:
        if grade.saturation < 1.0:
            grey = pygame.transform.grayscale(canvas)
            grey.set_alpha(round(255 * (1.0 - max(grade.saturation, 0.0))))
            canvas.blit(grey, (0, 0))
        if grade.multiply != (255, 255, 255):
            canvas.fill(grade.multiply, special_flags=pygame.BLEND_RGB_MULT)
        if grade.add != (0, 0, 0):
            canvas.fill(grade.add, special_flags=pygame.BLEND_RGB_ADD)

    @staticmethod
    def _build_vignette(size: tuple[int, int]) -> pygame.Surface:
        width, height = size
        small = pygame.Surface((width // 8 + 1, height // 8 + 1))
        cx, cy = (small.get_width() - 1) / 2, (small.get_height() - 1) / 2
        for y in range(small.get_height()):
            for x in range(small.get_width()):
                d = (((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2) ** 0.5 / 2**0.5
                shade = 255 * (1 - VIGNETTE_STRENGTH * clamp(d, 0.0, 1.0) ** 2)
                small.set_at((x, y), (round(shade),) * 3)
        return pygame.transform.smoothscale(small, size)

    @staticmethod
    def _build_scanlines(size: tuple[int, int]) -> pygame.Surface:
        lines = pygame.Surface(size)
        lines.fill((255, 255, 255))
        for y in range(1, size[1], 2):
            lines.fill((SCANLINE_SHADE,) * 3, (0, y, size[0], 1))
        return lines
