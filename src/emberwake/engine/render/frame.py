"""What gameplay asks a render backend to draw this frame (ADR 0008).

A frame is plain data in screen pixels: sprites sorted into layers, lights and flags. Gameplay
fills one per draw; a backend (software now, GL later) turns it into pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag, auto

import pygame


class Layer(IntEnum):
    """Draw order, back to front. Lights shine on everything below `ACTORS`."""

    WORLD = 0
    ACTORS = 1
    FOREGROUND = 2
    OVERLAY = 3


class Flag(IntFlag):
    """Effects a backend may honour; one that cannot do an effect ignores its flag."""

    LIGHTING = auto()
    BLOOM = auto()
    GRADING = auto()
    DEPTH_OF_FIELD = auto()


@dataclass(frozen=True, slots=True)
class SpriteCmd:
    """An image with its top-left corner at screen `(x, y)`."""

    image: pygame.Surface
    x: int
    y: int
    layer: Layer = Layer.ACTORS


@dataclass(frozen=True, slots=True)
class LightCmd:
    """A soft additive light centred at screen `(x, y)`.

    Attributes:
        radius: Reach in px.
        color: RGB of the light at full strength.
        intensity: 0 to 1; gameplay folds flicker and fades into it.
    """

    x: float
    y: float
    radius: int
    color: tuple[int, int, int]
    intensity: float = 1.0


@dataclass(slots=True)
class RenderFrame:
    """Everything to draw this frame, in screen px."""

    sprites: list[SpriteCmd] = field(default_factory=list)
    lights: list[LightCmd] = field(default_factory=list)
    flags: Flag = Flag.LIGHTING

    def sprite(
        self, image: pygame.Surface, x: float, y: float, layer: Layer = Layer.ACTORS
    ) -> None:
        """Queue `image` with its top-left corner at `(x, y)`."""
        self.sprites.append(SpriteCmd(image, round(x), round(y), layer))

    def light(
        self,
        x: float,
        y: float,
        radius: int,
        color: tuple[int, int, int],
        intensity: float = 1.0,
    ) -> None:
        """Queue a light centred at `(x, y)`."""
        self.lights.append(LightCmd(x, y, radius, color, intensity))

    def clear(self) -> None:
        """Forget every command, keeping the flags."""
        self.sprites.clear()
        self.lights.clear()
