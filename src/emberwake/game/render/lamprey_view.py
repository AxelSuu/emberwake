"""Drawing the Lamprey: a rig for the head, a verlet chain for the body, a dark water overlay.

Placeholder parts on an `engine.render.rig` rig (head, jaw, a lure on two bones, a fin) whose
clips follow the Lamprey's mode, and a `Chain` anchored behind the head so the segments trail it
with inertia. All of it is visual; the simulation never reads it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.render.frame import Layer
from emberwake.engine.render.hit_flash import flashed
from emberwake.engine.render.rig import Bone, Key, Part, Rig, RigClip, RotSpriteCache
from emberwake.engine.render.verlet import Chain
from emberwake.game import palette

if TYPE_CHECKING:
    from emberwake.engine.physics import Body
    from emberwake.engine.render.frame import RenderFrame
    from emberwake.game.lamprey import Lamprey

BONE = pygame.Color(palette.MIST)
BONE_DARK = pygame.Color("#9babb2")
SOCKET = pygame.Color(palette.INK)
EYE = pygame.Color(palette.EMBER_HOT)
BULB = pygame.Color("#fbb954")
WATER = pygame.Color(palette.INK)
WATER_LINE = pygame.Color(palette.DUSK)
WATER_ALPHA = 150
CANVAS = (72, 56)
"""Size of the head's drawing surface; the rig's origin is its centre."""
LINKS = 7
LINK = 11.0
RADII = (7, 7, 6, 5, 4, 3, 3, 2)
"""Segment radii from the neck to the tail tip, px."""
TELEPORT = 64.0
"""A head that jumps this far in one step drags nothing: the chain is put straight."""
BITING = frozenset({"lunge", "breach", "thrash"})
GAPING = frozenset({"stunned", "dazed", "gasp"})


def build_rig() -> Rig:
    return Rig(
        [
            Bone("head"),
            Bone("jaw", "head", (4.0, 3.0)),
            Bone("lure", "head", (-2.0, -5.0), -70.0),
            Bone("bulb", "lure", (9.0, 0.0), 10.0),
            Bone("fin", "head", (-4.0, 4.0), 110.0),
        ],
        [
            Part("fin", "fin", (7.0, 2.0), z=0),
            Part("head", "head", (13.0, 7.0), z=1),
            Part("jaw", "jaw", (0.0, 3.0), z=2),
            Part("lure", "stalk", (0.0, 1.0), z=0),
            Part("bulb", "bulb", (0.0, 2.0), z=3),
        ],
    )


def build_clips() -> dict[str, RigClip]:
    return {
        "idle": RigClip(
            2.0,
            {
                "jaw": [Key(0.0, 6.0), Key(1.0, 12.0), Key(2.0, 6.0)],
                "lure": [Key(0.0, -70.0), Key(1.0, -50.0), Key(2.0, -70.0)],
                "bulb": [Key(0.0, 14.0), Key(1.0, -14.0), Key(2.0, 14.0)],
            },
        ),
        "bite": RigClip(
            0.4,
            {"jaw": [Key(0.0, 12.0), Key(0.15, 50.0)], "lure": [Key(0.0, -80.0)]},
            loop=False,
        ),
        "gape": RigClip(
            1.0,
            {"jaw": [Key(0.0, 55.0), Key(0.5, 62.0), Key(1.0, 55.0)], "lure": [Key(0.0, -20.0)]},
        ),
    }


def build_images() -> dict[str, pygame.Surface]:
    head = pygame.Surface((26, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(head, BONE, (0, 0, 26, 14))
    pygame.draw.ellipse(head, BONE_DARK, (0, 7, 26, 7), 1)
    head.fill(SOCKET, (16, 3, 5, 4))
    head.fill(EYE, (18, 4, 2, 2))
    jaw = pygame.Surface((16, 6), pygame.SRCALPHA)
    pygame.draw.polygon(jaw, BONE, [(0, 0), (16, 2), (14, 6), (0, 6)])
    for x in range(3, 15, 3):
        jaw.fill(SOCKET, (x, 0, 1, 2))
    stalk = pygame.Surface((10, 2), pygame.SRCALPHA)
    stalk.fill(BONE_DARK)
    bulb = pygame.Surface((4, 4), pygame.SRCALPHA)
    pygame.draw.circle(bulb, BULB, (2, 2), 2)
    fin = pygame.Surface((8, 4), pygame.SRCALPHA)
    pygame.draw.polygon(fin, BONE_DARK, [(8, 2), (0, 0), (0, 4)])
    return {"head": head, "jaw": jaw, "stalk": stalk, "bulb": bulb, "fin": fin}


def _segment(radius: int, color: pygame.Color) -> pygame.Surface:
    image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(image, color, (radius, radius), radius)
    pygame.draw.circle(image, SOCKET, (radius, radius), radius, 1)
    return image


class LampreyView:
    """The look of one Lamprey, advanced with the simulation and queued each frame."""

    def __init__(self) -> None:
        self.rig, self.clips, self.images = build_rig(), build_clips(), build_images()
        self.cache = RotSpriteCache()
        self.chain: Chain | None = None
        self.segments = {r: _segment(r, BONE if r % 2 else BONE_DARK) for r in set(RADII)}
        self.water: dict[tuple[int, int], pygame.Surface] = {}

    def update(self, body: Body, lamprey: Lamprey, dt: float) -> None:
        """Pull the body chain along behind the head."""
        anchor = (body.center_x - lamprey.facing * 12, body.y + body.height / 2 + 2)
        if self.chain is None:
            self.chain = Chain(anchor, LINKS, LINK, gravity=70.0, damping=0.9)
        elif math.dist(self.chain.points[0], anchor) > TELEPORT:
            self.chain.reset(anchor)
        self.chain.update(anchor, dt)

    def pose(self, lamprey: Lamprey) -> dict[str, float]:
        """Bone angles for the mode: the clip at the time in it, the head tilted its way."""
        name = "bite" if lamprey.mode in BITING else "gape" if lamprey.mode in GAPING else "idle"
        return {**self.clips[name].sample(lamprey.since), "head": lamprey.heading}

    def queue(
        self,
        frame: RenderFrame,
        body: Body,
        lamprey: Lamprey,
        offset: tuple[int, int],
        flash: float = 0.0,
    ) -> None:
        """Queue the body segments, then the head, in screen space."""
        ox, oy = offset
        if self.chain is not None:
            for radius, (x, y) in reversed(list(zip(RADII, self.chain.points, strict=False))):
                image = self.segments[radius]
                frame.sprite(image, x - radius - ox, y - radius - oy)
        canvas = pygame.Surface(CANVAS, pygame.SRCALPHA)
        pose = self.pose(lamprey)
        self.rig.draw(canvas, self.images, (CANVAS[0] / 2, CANVAS[1] / 2), pose, self.cache)
        if lamprey.facing < 0:
            canvas = pygame.transform.flip(canvas, True, False)
        if flash > 0:
            canvas = flashed(canvas, flash)
        cx, cy = body.center_x - ox, body.y + body.height / 2 - oy
        frame.sprite(canvas, cx - CANVAS[0] / 2, cy - CANVAS[1] / 2)

    def queue_water(
        self, frame: RenderFrame, body: Body, lamprey: Lamprey, offset: tuple[int, int]
    ) -> None:
        """A dark veil over everything under the water line, until the arena drains."""
        if lamprey.arena is None or lamprey.drained:
            return
        left, top, width, height = lamprey.arena
        line = lamprey.home[1] + body.height / 2
        size = (round(width), round(top + height - line))
        if size not in self.water:
            veil = pygame.Surface(size, pygame.SRCALPHA)
            veil.fill((*WATER[:3], WATER_ALPHA))
            veil.fill(WATER_LINE, (0, 0, size[0], 1))
            self.water[size] = veil
        frame.sprite(self.water[size], left - offset[0], line - offset[1], Layer.FOREGROUND)
