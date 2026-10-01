"""Title screen: a dark skyline with embers drifting up past the logo."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import Scene
from emberwake.game import palette

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

EMBER_RAMP = tuple(
    pygame.Color(c)
    for c in (palette.EMBER_CORE, palette.EMBER_HOT, palette.EMBER_WARM, palette.EMBER_COOL)
)
MAX_EMBERS = 90


@dataclass(slots=True)
class Ember:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    phase: float

    def color(self) -> pygame.Color:
        t = 1 - self.life / self.max_life
        scaled = t * (len(EMBER_RAMP) - 1)
        i = min(int(scaled), len(EMBER_RAMP) - 2)
        return EMBER_RAMP[i].lerp(EMBER_RAMP[i + 1], scaled - i)


class TitleScene(Scene):
    def __init__(self, ctx: GameContext) -> None:
        self.ctx = ctx
        self.rng = random.Random(7)
        self.time = 0.0
        self.embers: list[Ember] = []
        self.background: pygame.Surface | None = None
        self.skylines: list[pygame.Surface] = []
        title_font = pygame.font.Font(None, 64)
        self.title = title_font.render("EMBERWAKE", False, palette.EMBER_HOT)
        self.glow = _glow(title_font.render("EMBERWAKE", False, palette.EMBER_WARM), 6)
        self.prompt = pygame.font.Font(None, 16).render("press any key", False, palette.MIST)
        self.glow_frame = self.glow.copy()
        self.ember_glow = _radial_glow(6, pygame.Color(palette.EMBER_WARM))

    def on_enter(self) -> None:
        size = self.ctx.canvas_size
        self.background = _gradient(size, pygame.Color(palette.INK), pygame.Color(palette.HORIZON))
        self.skylines = [
            _skyline(size, self.rng, pygame.Color(palette.PLUM), height=110, gap=(6, 18)),
            _skyline(size, self.rng, pygame.Color(palette.INK), height=70, gap=(2, 10)),
        ]

    def handle(self, event: pygame.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.manager.pop()

    def update(self, dt: float) -> None:
        self.time += dt
        width, height = self.ctx.canvas_size
        if len(self.embers) < MAX_EMBERS and self.rng.random() < 0.6:
            life = self.rng.uniform(2.5, 5.0)
            self.embers.append(
                Ember(
                    x=self.rng.uniform(0, width),
                    y=height + 4,
                    vx=self.rng.uniform(-6, 6),
                    vy=-self.rng.uniform(18, 42),
                    life=life,
                    max_life=life,
                    phase=self.rng.uniform(0, math.tau),
                )
            )
        for ember in self.embers:
            ember.life -= dt
            ember.x += (ember.vx + math.sin(self.time * 2 + ember.phase) * 10) * dt
            ember.y += ember.vy * dt
        self.embers = [e for e in self.embers if e.life > 0]

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        if self.background is None:
            return
        canvas.blit(self.background, (0, 0))
        width = canvas.get_width()
        for depth, skyline in enumerate(self.skylines, start=1):
            offset = -(self.time * 4 * depth) % width
            canvas.blit(skyline, (offset - width, 0))
            canvas.blit(skyline, (offset, 0))

        glow_offset = self.ember_glow.get_width() // 2
        for ember in self.embers:
            color = ember.color()
            canvas.blit(
                self.ember_glow,
                (ember.x - glow_offset, ember.y - glow_offset),
                special_flags=pygame.BLEND_RGB_ADD,
            )
            canvas.fill(color, (round(ember.x), round(ember.y), 1, 1))

        center = canvas.get_rect().center
        flicker = 0.75 + 0.25 * math.sin(self.time * 9) * math.sin(self.time * 3.7)
        level = round(255 * flicker)
        self.glow_frame.blit(self.glow, (0, 0))
        self.glow_frame.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
        title_pos = self.title.get_rect(center=(center[0], center[1] - 30))
        canvas.blit(
            self.glow_frame,
            self.glow.get_rect(center=title_pos.center),
            special_flags=pygame.BLEND_RGB_ADD,
        )
        canvas.blit(self.title, title_pos)
        if int(self.time * 1.5) % 2 == 0:
            canvas.blit(self.prompt, self.prompt.get_rect(center=(center[0], center[1] + 40)))


def _glow(image: pygame.Surface, radius: int) -> pygame.Surface:
    """Blurred copy of `image` on black with room for the blur, for additive blending."""
    padding = radius * 2
    width, height = image.get_size()
    surface = pygame.Surface((width + padding * 2, height + padding * 2)).convert()
    surface.blit(image, (padding, padding))
    return pygame.transform.gaussian_blur(surface, radius)


def _gradient(size: tuple[int, int], top: pygame.Color, bottom: pygame.Color) -> pygame.Surface:
    surface = pygame.Surface(size).convert()
    width, height = size
    for y in range(height):
        pygame.draw.line(surface, top.lerp(bottom, y / (height - 1)), (0, y), (width, y))
    return surface


def _skyline(
    size: tuple[int, int],
    rng: random.Random,
    color: pygame.Color,
    *,
    height: int,
    gap: tuple[int, int],
) -> pygame.Surface:
    width, canvas_height = size
    surface = pygame.Surface(size, pygame.SRCALPHA).convert_alpha()
    x = 0
    while x < width:
        w = rng.randint(14, 40)
        h = rng.randint(height // 3, height)
        top = canvas_height - h
        surface.fill(color, (x, top, w, h))
        if rng.random() < 0.3:
            surface.fill(color, (x + w // 2 - 1, top - rng.randint(6, 16), 2, 16))
        x += w + rng.randint(*gap)
    return surface


def _radial_glow(radius: int, color: pygame.Color) -> pygame.Surface:
    surface = pygame.Surface((radius * 2 + 1, radius * 2 + 1)).convert()
    black = pygame.Color("black")
    for r in range(radius, 0, -1):
        brightness = (1 - r / radius) ** 2 * 0.35
        pygame.draw.circle(surface, black.lerp(color, brightness), (radius, radius), r)
    return surface
