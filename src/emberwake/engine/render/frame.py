"""What gameplay asks a render backend to draw this frame (ADR 0008).

A frame is plain data in screen pixels: sprites sorted into layers, lights and flags. Gameplay
fills one per draw; a backend (software now, GL later) turns it into pixels.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag, auto

import pygame


class Layer(IntEnum):
    """Draw order, back to front.

    In the dark (`RenderFrame.ambient` below white) lights shine on `WORLD`, `ACTORS` and what the
    canvas held before; `GLOW` is drawn after the lighting at full brightness, for pixels that
    give off light (flames, eyes, embers). Without darkness lights only brighten `WORLD`.
    """

    WORLD = 0
    ACTORS = 1
    GLOW = 2
    FOREGROUND = 3
    OVERLAY = 4


class Flag(IntFlag):
    """Effects a backend may honour; one that cannot do an effect ignores its flag."""

    LIGHTING = auto()
    BLOOM = auto()
    GRADING = auto()
    DEPTH_OF_FIELD = auto()
    VIGNETTE = auto()
    CRT = auto()
    SHADOWS = auto()
    SHAFTS = auto()


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
        shadows: Whether solid things block this light (when the frame has occluders).
        key: For a light that does not move in the world: anything that names it and its
            place. Its shadows are then cast once and reused until `RenderFrame.occluder_version`
            changes.
    """

    x: float
    y: float
    radius: int
    color: tuple[int, int, int]
    intensity: float = 1.0
    shadows: bool = True
    key: Hashable | None = None


@dataclass(frozen=True, slots=True)
class ShaftCmd:
    """A soft beam of light from screen `(x, y)` along `angle` degrees (0 right, 90 down).

    Attributes:
        length: Reach in px.
        width: Width at the far end in px; the beam starts narrow.
        color: RGB at full strength.
        intensity: 0 to 1.
    """

    x: float
    y: float
    angle: float
    length: int
    width: int
    color: tuple[int, int, int]
    intensity: float = 1.0


@dataclass(slots=True)
class RenderFrame:
    """Everything to draw this frame, in screen px."""

    sprites: list[SpriteCmd] = field(default_factory=list)
    lights: list[LightCmd] = field(default_factory=list)
    shafts: list[ShaftCmd] = field(default_factory=list)
    flags: Flag = Flag.LIGHTING
    occluded: Callable[[float, float], bool] | None = None
    """Whether a screen px point blocks light; set per frame by gameplay."""
    ambient: tuple[int, int, int] = (255, 255, 255)
    """How lit things are where no light reaches; white means no darkness at all."""
    occluder_version: int = 0
    """Changes whenever what blocks light changes, so cached shadows of keyed lights refresh."""

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
        *,
        shadows: bool = True,
        key: Hashable | None = None,
    ) -> None:
        """Queue a light centred at `(x, y)`; see `LightCmd` for `key`."""
        self.lights.append(LightCmd(x, y, radius, color, intensity, shadows, key))

    def shaft(self, cmd: ShaftCmd) -> None:
        """Queue a light shaft; drawn after the lights, over the world layer."""
        self.shafts.append(cmd)

    def clear(self) -> None:
        """Forget every command, keeping the flags."""
        self.sprites.clear()
        self.lights.clear()
        self.shafts.clear()
        self.occluded = None
