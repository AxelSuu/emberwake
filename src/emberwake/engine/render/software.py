"""The software backend: blits, a multiplied light map for darkness, additive haze.

With darkness (`RenderFrame.ambient` below white) every light is added onto a light map filled
with the ambient color, shadows cut out of it, and the whole canvas is multiplied by the map:
what no light reaches sinks to the ambient. A faint additive haze around each light follows,
then the `GLOW` layer at full brightness. Without darkness, lights are only that haze over the
world layer, as before.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.render.frame import Flag, Layer
from emberwake.engine.render.shadows import shadow_mask
from emberwake.engine.render.shafts import ShaftCache

if TYPE_CHECKING:
    from collections.abc import Hashable

    from emberwake.engine.render.frame import LightCmd, RenderFrame

LEVELS = 6
"""Distinct intensities cached per light shape; flicker steps between them."""
STRENGTH = 0.35
"""Share of the light's color the haze adds at its centre at full intensity, without darkness."""
HAZE = 0.12
"""The same share in the dark, where the light map does most of the work."""
TINT = 0.5
"""How much of a light's color it lends to what it lights; the rest is white."""
REACH = 1.3
"""Light map gradients reach further than the haze..."""
POOL = -1.0
"""Marks the light map's falloff: a pool, bright in the middle, ``(1 - (r/R)^2)^2``."""
SHADOW_BUDGET = 6
"""Lights per frame that cast shadows, the biggest first; the rest shine through walls."""
WHITE = (255, 255, 255)


class SoftwareBackend:
    """Draws a `RenderFrame` onto a surface: layers in order, with lights and darkness."""

    def __init__(self) -> None:
        self._gradients: dict[tuple[str, int, tuple[int, int, int], int], pygame.Surface] = {}
        self._shafts = ShaftCache()
        self._map: pygame.Surface | None = None
        self._masks: dict[tuple[Hashable, int], pygame.Surface | None] = {}
        self._masks_version = 0

    def render(self, frame: RenderFrame, canvas: pygame.Surface) -> None:
        """Draw the frame's sprites and lights onto `canvas`, which keeps what it already shows."""
        lighting = Flag.LIGHTING in frame.flags
        dark = lighting and frame.ambient != WHITE
        lights = _visible(frame.lights, canvas.get_rect()) if lighting else []
        for layer in Layer:
            if layer is Layer.ACTORS and lighting and not dark:
                for light in lights:
                    self._haze(canvas, light, frame, STRENGTH)
            if layer is Layer.GLOW:
                if dark:
                    self._darken(canvas, frame, lights)
                    for light in lights:
                        self._haze(canvas, light, frame, HAZE, shadows=False)
                if Flag.SHAFTS in frame.flags:
                    for shaft in frame.shafts:
                        self._shafts.draw(canvas, shaft)
            canvas.fblits([(c.image, (c.x, c.y)) for c in frame.sprites if c.layer is layer])

    def _darken(self, canvas: pygame.Surface, frame: RenderFrame, lights: list[LightCmd]) -> None:
        """Multiply the canvas by a light map: the ambient, plus every light, minus shadows."""
        size = canvas.get_size()
        if self._map is None or self._map.get_size() != size:
            self._map = pygame.Surface(size, 0, canvas)
        light_map = self._map
        light_map.fill(frame.ambient)
        shadowed = set(sorted(lights, key=_weight, reverse=True)[:SHADOW_BUDGET])
        for light in lights:
            level = _level(light)
            if level == 0:
                continue
            radius = round(light.radius * REACH)
            image = self._gradient("map", canvas, radius, _tint(light.color), level, 1.0, POOL)
            if light in shadowed:
                image = self._shadowed(image, light, frame, canvas, radius)
            rect = image.get_rect(center=(round(light.x), round(light.y)))
            light_map.blit(image, rect, special_flags=pygame.BLEND_RGB_ADD)
        canvas.blit(light_map, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def _haze(
        self,
        canvas: pygame.Surface,
        light: LightCmd,
        frame: RenderFrame,
        strength: float,
        *,
        shadows: bool = True,
    ) -> None:
        """Add the light's color around it; in the dark this is faint, so it skips shadows."""
        level = _level(light)
        if level == 0:
            return
        image = self._gradient("haze", canvas, light.radius, light.color, level, strength, 2.0)
        if shadows:
            image = self._shadowed(image, light, frame, canvas, light.radius)
        rect = image.get_rect(center=(round(light.x), round(light.y)))
        canvas.blit(image, rect, special_flags=pygame.BLEND_RGB_ADD)

    def _shadowed(
        self,
        image: pygame.Surface,
        light: LightCmd,
        frame: RenderFrame,
        canvas: pygame.Surface,
        radius: int,
    ) -> pygame.Surface:
        if not light.shadows or Flag.SHADOWS not in frame.flags or frame.occluded is None:
            return image
        mask = self._mask(light, frame, canvas, radius)
        if mask is None:
            return image
        image = image.copy()
        image.blit(mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        return image

    def _mask(
        self, light: LightCmd, frame: RenderFrame, canvas: pygame.Surface, radius: int
    ) -> pygame.Surface | None:
        """The light's shadow mask, cast once per occluder version for keyed lights."""
        assert frame.occluded is not None
        if light.key is None:
            return shadow_mask(frame.occluded, light.x, light.y, radius, canvas)
        if frame.occluder_version != self._masks_version:
            self._masks.clear()
            self._masks_version = frame.occluder_version
        key = (light.key, radius)
        if key not in self._masks:
            self._masks[key] = shadow_mask(frame.occluded, light.x, light.y, radius, canvas)
        return self._masks[key]

    def _gradient(  # noqa: PLR0917
        self,
        kind: str,
        like: pygame.Surface,
        radius: int,
        color: tuple[int, int, int],
        level: int,
        strength: float,
        power: float,
    ) -> pygame.Surface:
        key = (f"{kind}:{strength}:{power}", radius, color, level)
        if key not in self._gradients:
            surface = pygame.Surface((radius * 2, radius * 2), 0, like)
            black, tint = pygame.Color("black"), pygame.Color(*color)
            scale = level / (LEVELS - 1) * strength
            for r in range(radius, 0, -1):
                t = r / radius
                falloff = (1 - t * t) ** 2 if power == POOL else (1 - t) ** power
                pygame.draw.circle(surface, black.lerp(tint, falloff * scale), (radius, radius), r)
            self._gradients[key] = surface
        return self._gradients[key]


def _level(light: LightCmd) -> int:
    return round(min(max(light.intensity, 0.0), 1.0) * (LEVELS - 1))


def _weight(light: LightCmd) -> float:
    return light.radius * light.intensity


def _tint(color: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = (round(255 + (c - 255) * TINT) for c in color)
    return r, g, b


def _visible(lights: list[LightCmd], screen: pygame.Rect) -> list[LightCmd]:
    """Lights whose reach touches the screen."""
    return [
        light
        for light in lights
        if screen.colliderect(
            pygame.Rect(
                light.x - light.radius * REACH,
                light.y - light.radius * REACH,
                light.radius * 2 * REACH,
                light.radius * 2 * REACH,
            )
        )
    ]
