"""The software backend: blits, with lights approximated by additive gradients."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.render.frame import Flag, Layer

if TYPE_CHECKING:
    from emberwake.engine.render.frame import LightCmd, RenderFrame

LEVELS = 6
"""Distinct intensities cached per light shape; flicker steps between them."""
STRENGTH = 0.35
"""Share of the light's color a gradient adds at its centre at full intensity."""


class SoftwareBackend:
    """Draws a `RenderFrame` onto a surface: the layers in order, lights over the world layer."""

    def __init__(self) -> None:
        self._gradients: dict[tuple[int, tuple[int, int, int], int], pygame.Surface] = {}

    def render(self, frame: RenderFrame, canvas: pygame.Surface) -> None:
        """Draw the frame's sprites and lights onto `canvas`, which keeps what it already shows."""
        for layer in Layer:
            if layer is Layer.ACTORS and Flag.LIGHTING in frame.flags:
                for light in frame.lights:
                    self._light(canvas, light)
            canvas.fblits([(c.image, (c.x, c.y)) for c in frame.sprites if c.layer is layer])

    def _light(self, canvas: pygame.Surface, light: LightCmd) -> None:
        level = round(min(max(light.intensity, 0.0), 1.0) * (LEVELS - 1))
        if level == 0:
            return
        image = self._gradient(canvas, light.radius, light.color, level)
        rect = image.get_rect(center=(round(light.x), round(light.y)))
        canvas.blit(image, rect, special_flags=pygame.BLEND_RGB_ADD)

    def _gradient(
        self, like: pygame.Surface, radius: int, color: tuple[int, int, int], level: int
    ) -> pygame.Surface:
        key = (radius, color, level)
        if key not in self._gradients:
            surface = pygame.Surface((radius * 2, radius * 2), 0, like)
            black, tint = pygame.Color("black"), pygame.Color(*color)
            strength = level / (LEVELS - 1)
            for r in range(radius, 0, -1):
                falloff = (1 - r / radius) ** 2
                pygame.draw.circle(
                    surface, black.lerp(tint, falloff * STRENGTH * strength), (radius, radius), r
                )
            self._gradients[key] = surface
        return self._gradients[key]
