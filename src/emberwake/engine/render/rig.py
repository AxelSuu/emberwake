"""Skeletal rigs: bones, sprite parts, keyframed poses and crisp pixel-art rotation.

A `Rig` is a bone tree plus the sprite `Part` attached to each bone. A `RigClip` keys bone
angles over time; sampling it gives a pose, `Rig.solve` turns a pose into world transforms, and
`Rig.draw` blits each part rotated about its pivot. Rotation goes through `RotSpriteCache`, which
upscales with scale2x before rotating so pixel art keeps hard edges, and caches the results.

Angles are degrees, clockwise on screen (y points down).
"""

from __future__ import annotations

import math
import tomllib
from collections import OrderedDict
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

UPSCALE_PASSES = 3
"""scale2x passes before rotating: the image is rotated at 8x, then sampled back down."""


@dataclass(slots=True)
class Bone:
    """A joint. `offset` is where it sits in its parent's frame, before the parent rotates."""

    name: str
    parent: str = ""
    offset: tuple[float, float] = (0.0, 0.0)
    angle: float = 0.0
    """Rest angle."""


@dataclass(slots=True)
class Part:
    """A sprite hung on a bone, rotating about `pivot` (a point in the image)."""

    bone: str
    image: str
    pivot: tuple[float, float] = (0.0, 0.0)
    z: int = 0


@dataclass(slots=True)
class Key:
    """A bone angle at a time in the clip."""

    time: float
    angle: float


@dataclass(slots=True)
class RigClip:
    """Keyframed bone angles: for each bone, keys sorted by time."""

    duration: float
    tracks: dict[str, list[Key]] = field(default_factory=dict)
    loop: bool = True

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise ValueError("a clip needs a positive duration")
        for bone, keys in self.tracks.items():
            if [k.time for k in keys] != sorted(k.time for k in keys):
                raise ValueError(f"keys for {bone!r} must be sorted by time")

    def sample(self, t: float) -> dict[str, float]:
        """Bone angles at time `t`, interpolating between keys along the shorter way round."""
        t = t % self.duration if self.loop else min(max(t, 0.0), self.duration)
        return {bone: _angle_at(keys, t) for bone, keys in self.tracks.items() if keys}


@dataclass(frozen=True, slots=True)
class Transform:
    """Where a bone's joint is in the rig's space, and which way it points."""

    x: float
    y: float
    angle: float


@dataclass(slots=True)
class Rig:
    """Bones in parent-before-child order, and the parts drawn on them."""

    bones: list[Bone]
    parts: list[Part] = field(default_factory=list)

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for bone in self.bones:
            if bone.name in seen:
                raise ValueError(f"duplicate bone {bone.name!r}")
            if bone.parent and bone.parent not in seen:
                raise ValueError(f"bone {bone.name!r} needs its parent {bone.parent!r} first")
            seen.add(bone.name)
        for part in self.parts:
            if part.bone not in seen:
                raise ValueError(f"part {part.image!r} is on unknown bone {part.bone!r}")

    def solve(self, pose: Mapping[str, float] | None = None) -> dict[str, Transform]:
        """World transform of every bone. `pose` gives angles that replace the rest angles."""
        pose = pose or {}
        out: dict[str, Transform] = {}
        for bone in self.bones:
            angle = pose.get(bone.name, bone.angle)
            if bone.parent:
                parent = out[bone.parent]
                dx, dy = _rotate(bone.offset, parent.angle)
                out[bone.name] = Transform(parent.x + dx, parent.y + dy, parent.angle + angle)
            else:
                out[bone.name] = Transform(bone.offset[0], bone.offset[1], angle)
        return out

    def draw(
        self,
        canvas: pygame.Surface,
        images: Mapping[str, pygame.Surface],
        origin: tuple[float, float],
        pose: Mapping[str, float] | None = None,
        cache: RotSpriteCache | None = None,
    ) -> None:
        """Blit every part, back to front, with the rig's space placed at `origin` on `canvas`."""
        cache = cache or RotSpriteCache()
        transforms = self.solve(pose)
        for part in sorted(self.parts, key=lambda p: p.z):
            at = transforms[part.bone]
            image = images[part.image]
            rotated = cache.rotate(part.image, image, at.angle)
            width, height = image.get_size()
            to_pivot = (part.pivot[0] - width / 2, part.pivot[1] - height / 2)
            dx, dy = _rotate(to_pivot, cache.quantize(at.angle))
            centre = (origin[0] + at.x - dx, origin[1] + at.y - dy)
            canvas.blit(rotated, rotated.get_rect(center=(round(centre[0]), round(centre[1]))))


def load_rig(path: Path) -> tuple[Rig, dict[str, RigClip]]:
    """Read a rig and its clips from TOML (``[[bones]]``, ``[[parts]]``, ``[clips.name]``)."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rig = from_data(Rig, {"bones": data.get("bones", []), "parts": data.get("parts", [])})
    return rig, from_data(dict[str, RigClip], data.get("clips", {}))


class RotSpriteCache:
    """Rotates pixel-art sprites without smearing them, and remembers the results.

    Angles are rounded to `step` degrees, so a sprite has at most ``360 / step`` cached
    rotations; the least recently used entries go once `capacity` is reached.
    """

    def __init__(self, step: float = 5.0, capacity: int = 256) -> None:
        self.step = step
        self.capacity = capacity
        self._cache: OrderedDict[tuple[str, float], pygame.Surface] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def quantize(self, angle: float) -> float:
        """`angle` rounded to the cache's step, within -180 to 180."""
        snapped = round(angle / self.step) * self.step
        return (snapped + 180.0) % 360.0 - 180.0

    def rotate(self, key: str, image: pygame.Surface, angle: float) -> pygame.Surface:
        """`image` rotated by `angle`; `key` names the image for caching (one key, one image)."""
        snapped = self.quantize(angle)
        entry = (key, snapped)
        cached = self._cache.get(entry)
        if cached is not None:
            self._cache.move_to_end(entry)
            self.hits += 1
            return cached
        self.misses += 1
        result = rotsprite(image, snapped)
        self._cache[entry] = result
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)
        return result

    def __len__(self) -> int:
        return len(self._cache)


def rotsprite(image: pygame.Surface, angle: float) -> pygame.Surface:
    """Rotate pixel art by `angle` degrees clockwise: scale2x up, rotate hard, sample back down."""
    if angle % 360 == 0:
        return image
    big = image
    for _ in range(UPSCALE_PASSES):
        big = pygame.transform.scale2x(big)
    big = pygame.transform.rotate(big, -angle)
    factor = 2**UPSCALE_PASSES
    return pygame.transform.scale(big, (big.get_width() // factor, big.get_height() // factor))


def _rotate(point: tuple[float, float], degrees: float) -> tuple[float, float]:
    rad = math.radians(degrees)
    cos, sin = math.cos(rad), math.sin(rad)
    return point[0] * cos - point[1] * sin, point[0] * sin + point[1] * cos


def _angle_at(keys: list[Key], t: float) -> float:
    if t <= keys[0].time:
        return keys[0].angle
    for before, after in pairwise(keys):
        if t <= after.time:
            span = after.time - before.time
            blend = (t - before.time) / span if span > 0 else 1.0
            delta = (after.angle - before.angle + 180.0) % 360.0 - 180.0
            return before.angle + delta * blend
    return keys[-1].angle
