"""Drawing the player: body, scarf, swinging lantern and its light, swings, dash afterimages.

The look is the placeholder `PlayerSprite` until finished sheets ``player_<state>`` exist in
the sprite bank (states from `anim_state`). Secondary motion works on either: a verlet scarf
trails from the neck, the lantern hangs from the hand on a pendulum (and its light sways with
it), the body breathes and bobs with the run cycle, and a dash leaves fading afterimages.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.render.frame import Layer
from emberwake.engine.render.verlet import Chain
from emberwake.game.player.controller import PlayerState
from emberwake.game.player.visual import anim_state
from emberwake.game.render.swing_fx import arm, lantern_point, trail

if TYPE_CHECKING:
    from emberwake.engine.physics import Body
    from emberwake.engine.render.frame import RenderFrame
    from emberwake.game.player.controller import Motor
    from emberwake.game.player.kindle import Kindle
    from emberwake.game.player.swing import Swing, SwingTuning
    from emberwake.game.player.visual import PlayerVisual
    from emberwake.game.render.bank import SpriteBank
    from emberwake.game.render.glow import Glows
    from emberwake.game.render.placeholder import PlayerSprite

SHOULDER = (2, -12)
"""The shoulder relative to the feet for a right-facing player, px."""
NECK = (-1, -15)
SWING_PIVOT = 13
"""Px above the feet that a swing turns around."""
HANDLE = 2.5
"""Px from the hand down to the lantern's centre."""
SCARF = ("#b33831", "#6e2727")
SCARF_LINKS = 5
SCARF_LINK = 2.5
AFTERIMAGE = (48, 225, 185)
AFTERIMAGE_LIFE = 0.22
AFTERIMAGE_EVERY = 2
"""Ticks between afterimages while dashing."""
AFTERIMAGE_ALPHA = 90
AFTERIMAGE_DELAY = 0.05
"""Seconds before an afterimage shows, so it never covers the player."""


@dataclass(slots=True)
class Light:
    """The lantern's light this frame."""

    radius: int
    color: tuple[int, int, int]
    intensity: float


@dataclass(slots=True)
class _Afterimage:
    image: pygame.Surface
    x: float
    y: float
    life: float = AFTERIMAGE_LIFE


class PlayerView:
    """Owns the player's secondary motion and queues the player into a `RenderFrame`."""

    def __init__(self, sprite: PlayerSprite, bank: SpriteBank, glows: Glows) -> None:
        self.sprite = sprite
        self.bank = bank
        self.glows = glows
        self.scarf = Chain((0.0, 0.0), SCARF_LINKS, SCARF_LINK, gravity=260.0, damping=0.82)
        self.afterimages: list[_Afterimage] = []
        self.state = "idle"
        self.since = 0.0
        self._ticks = 0
        self._placed = False

    def place(self, body: Body, motor: Motor) -> None:
        """Settle the scarf at the player's position (after spawning or a teleport)."""
        self.scarf.reset(self._neck(body, motor))
        self._placed = True

    def update(
        self, body: Body, motor: Motor, swing: Swing | None, kindle: Kindle | None, dt: float
    ) -> None:
        """One tick of the scarf, afterimages and the animation state."""
        if not self._placed:
            self.place(body, motor)
        self.scarf.wind = -motor.vx * 2.0
        self.scarf.update(self._neck(body, motor), dt)
        state = anim_state(motor, swing, kindle)
        self.since = 0.0 if state != self.state else self.since + dt
        self.state = state
        self._ticks += 1
        for ghost in self.afterimages:
            ghost.life -= dt
        self.afterimages = [ghost for ghost in self.afterimages if ghost.life > 0]
        if motor.state is PlayerState.DASH and self._ticks % AFTERIMAGE_EVERY == 0:
            image = _silhouette(self.sprite.image(motor.facing, 1.0, 1.0, bare=True))
            self.afterimages.append(_Afterimage(image, body.center_x, body.bottom))

    def queue(  # noqa: PLR0917
        self,
        frame: RenderFrame,
        body: Body,
        motor: Motor,
        visual: PlayerVisual,
        swing: Swing | None,
        tuning: SwingTuning,
        *,
        offset: tuple[int, int],
        alpha: float,
        light: Light,
    ) -> None:
        ox, oy = offset
        px, py = motor.previous
        x = px + (body.x - px) * alpha
        y = py + (body.y - py) * alpha
        feet = (x + body.width / 2 - ox, y + body.height - oy - visual.bob)
        drift = (x - body.x, y - body.y)
        self._queue_afterimages(frame, ox, oy)
        self._queue_scarf(frame, ox - drift[0], oy - drift[1] + visual.bob)
        swinging = swing is not None and swing.tick > 0
        finished = self.bank.image(f"player_{self.state}", self.since)
        lantern = self._lantern(feet, motor, visual)
        if swing is not None and swinging:
            pivot = (feet[0], feet[1] - SWING_PIVOT)
            lantern = lantern_point(swing, tuning, pivot, lantern)
            if (arc := trail(swing, tuning)) is not None:
                frame.sprite(*_centred(arc, pivot), layer=Layer.GLOW)
        frame.light(*lantern, light.radius, light.color, light.intensity)
        if finished is not None:
            image = pygame.transform.flip(finished, True, False) if motor.facing < 0 else finished
            self._lit(frame, *_at(image, feet))
            return
        scale_y = visual.scale_y + visual.breath
        image = self.sprite.image(motor.facing, visual.scale_x, scale_y, bare=True)
        self._lit(frame, *_at(image, feet))
        shoulder = (round(feet[0] + SHOULDER[0] * motor.facing), round(feet[1] + SHOULDER[1]))
        hand = (lantern[0], lantern[1] - HANDLE)
        line, (left, top) = arm(hand[0] - shoulder[0], hand[1] - shoulder[1])
        frame.sprite(line, shoulder[0] + left, shoulder[1] + top)
        self._lit(frame, *_centred(self.sprite.lantern, lantern))

    def _lantern(
        self, feet: tuple[float, float], motor: Motor, visual: PlayerVisual
    ) -> tuple[float, float]:
        """The lantern's centre, hanging from the hand at the pendulum's angle."""
        lx, ly = self.sprite.lantern_offset(motor.facing, visual.scale_x, visual.scale_y)
        hand = (feet[0] + lx, feet[1] + ly - HANDLE)
        angle = visual.lantern_angle
        return hand[0] + math.sin(angle) * HANDLE, hand[1] + math.cos(angle) * HANDLE

    @staticmethod
    def _neck(body: Body, motor: Motor) -> tuple[float, float]:
        return body.center_x + NECK[0] * motor.facing, body.bottom + NECK[1]

    def _queue_scarf(self, frame: RenderFrame, ox: float, oy: float) -> None:
        points = [(px - ox, py - oy) for px, py in self.scarf.points]
        left = math.floor(min(p[0] for p in points)) - 1
        top = math.floor(min(p[1] for p in points)) - 1
        width = math.ceil(max(p[0] for p in points)) - left + 2
        height = math.ceil(max(p[1] for p in points)) - top + 2
        image = pygame.Surface((width, height), pygame.SRCALPHA)
        local = [(px - left, py - top) for px, py in points]
        half = len(local) // 2
        pygame.draw.lines(image, SCARF[0], False, local[: half + 1], 2)
        pygame.draw.lines(image, SCARF[1], False, local[half:], 1)
        frame.sprite(image, left, top)

    def _queue_afterimages(self, frame: RenderFrame, ox: int, oy: int) -> None:
        for ghost in self.afterimages:
            if ghost.life > AFTERIMAGE_LIFE - AFTERIMAGE_DELAY:
                continue
            image = ghost.image.copy()
            image.set_alpha(round(AFTERIMAGE_ALPHA * ghost.life / AFTERIMAGE_LIFE))
            frame.sprite(*_at(image, (ghost.x - ox, ghost.y - oy)), layer=Layer.GLOW)

    def _lit(self, frame: RenderFrame, image: pygame.Surface, x: int, y: int) -> None:
        frame.sprite(image, x, y)
        if (glow := self.glows(image)) is not None:
            frame.sprite(glow, x, y, Layer.GLOW)


@functools.cache
def _silhouette(image: pygame.Surface) -> pygame.Surface:
    return pygame.mask.from_surface(image).to_surface(
        setcolor=(*AFTERIMAGE, 255), unsetcolor=(0, 0, 0, 0)
    )


def _at(image: pygame.Surface, midbottom: tuple[float, float]) -> tuple[pygame.Surface, int, int]:
    rect = image.get_rect(midbottom=(round(midbottom[0]), round(midbottom[1])))
    return image, rect.x, rect.y


def _centred(image: pygame.Surface, centre: tuple[float, float]) -> tuple[pygame.Surface, int, int]:
    rect = image.get_rect(center=(round(centre[0]), round(centre[1])))
    return image, rect.x, rect.y
