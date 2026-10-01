"""Light shafts for the software backend: cached soft beams drawn additively."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from emberwake.engine.render.frame import ShaftCmd

LEVELS = 6
ANGLE_STEP = 5
"""Beams are cached at multiples of this many degrees."""
STRENGTH = 0.22
"""Share of the beam's color added at its brightest point at full intensity."""


class ShaftCache:
    """Beam images by shape, strength and angle, rotated once and reused."""

    def __init__(self) -> None:
        self._beams: dict[tuple[int, int, tuple[int, int, int], int, int], pygame.Surface] = {}

    def draw(self, canvas: pygame.Surface, cmd: ShaftCmd) -> None:
        """Add the beam `cmd` to `canvas`."""
        level = round(min(max(cmd.intensity, 0.0), 1.0) * (LEVELS - 1))
        if level == 0:
            return
        angle = round(cmd.angle / ANGLE_STEP) * ANGLE_STEP % 360
        beam = self._beam(canvas, cmd, level, angle)
        # The beam image points right from its left edge's centre; rotation keeps that centre.
        centre = pygame.Vector2(cmd.x, cmd.y) + pygame.Vector2(cmd.length / 2, 0).rotate(angle)
        canvas.blit(
            beam,
            beam.get_rect(center=(round(centre.x), round(centre.y))),
            special_flags=pygame.BLEND_RGB_ADD,
        )

    def _beam(self, like: pygame.Surface, cmd: ShaftCmd, level: int, angle: int) -> pygame.Surface:
        key = (cmd.length, cmd.width, cmd.color, level, angle)
        if key not in self._beams:
            flat = self._flat(like, cmd, level)
            self._beams[key] = pygame.transform.rotate(flat, -angle) if angle else flat
        return self._beams[key]

    @staticmethod
    def _flat(like: pygame.Surface, cmd: ShaftCmd, level: int) -> pygame.Surface:
        """A beam pointing right: a thin start widening and fading to nothing at the far end."""
        length, width = cmd.length, cmd.width
        surface = pygame.Surface((length, width), 0, like)
        surface.fill((0, 0, 0))
        tint, black = pygame.Color(*cmd.color), pygame.Color("black")
        strength = STRENGTH * level / (LEVELS - 1)
        for x in range(length):
            along = x / max(length - 1, 1)
            half = max(width * along / 2, 0.5)
            fade = (1.0 - along) ** 1.5
            for y in range(width):
                edge = 1.0 - min(abs(y - (width - 1) / 2) / half, 1.0)
                if edge > 0:
                    surface.set_at((x, y), black.lerp(tint, fade * edge * edge * strength))
        return surface
