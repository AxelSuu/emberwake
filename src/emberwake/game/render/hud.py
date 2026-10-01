"""The heads-up display: health, flame, flares, embers and area banners.

Top left, small and quiet so the dark stays dark: a row of lantern-shaped health pips, the flame
as a wick under them that pulses when low and blinks while guttering, the flares beside it, and
the ember count, which shows only for a while after it changes. Banners fade in at the top
centre when the player enters a new area.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from emberwake.game import palette

ORIGIN = (6, 6)
PIP = (7, 9)
PIP_GAP = 2
WICK_HEIGHT = 3
WICK_PER_FLAME = 0.4
"""Px of wick per point of maximum flame, so oil upgrades lengthen it."""
LOW = 0.25
EMBERS_SHOWN = 2.5
"""Seconds the ember count stays after it changes."""
BANNER_SHOWN = 2.6
FADE = 0.4

_FRAME = pygame.Color("#625565")
_GLASS_DARK = pygame.Color(palette.NIGHT)
_HOT = pygame.Color(palette.EMBER_HOT)
_CORE = pygame.Color(palette.EMBER_CORE)
_WARM = pygame.Color(palette.EMBER_WARM)
_COOL = pygame.Color(palette.EMBER_COOL)
_INK = pygame.Color(palette.INK)
_MIST = pygame.Color(palette.MIST)


@dataclass(slots=True)
class HudState:
    """What the HUD shows this frame."""

    health: int
    max_health: int
    flame: float
    max_flame: float
    flares: int
    max_flares: int
    refill: float = 0.0
    """0 to 1 toward the next flare."""
    embers: int = 0


def _pip(full: bool) -> pygame.Surface:
    """A tiny lantern: lit when the health it stands for is there."""
    image = pygame.Surface(PIP, pygame.SRCALPHA)
    w, h = PIP
    image.fill(_INK, (1, 0, w - 2, h))
    image.fill(_INK, (0, 2, w, h - 3))
    image.fill(_FRAME, (2, 1, w - 4, 1))
    image.fill(_FRAME, (2, h - 2, w - 4, 1))
    glass = (1, 3, w - 2, h - 5)
    if full:
        image.fill(_HOT, glass)
        image.fill(_CORE, (3, 4, 1, 2))
    else:
        image.fill(_GLASS_DARK, glass)
    return image


def _flare(full: bool) -> pygame.Surface:
    image = pygame.Surface((3, 7), pygame.SRCALPHA)
    image.fill(_INK, (0, 2, 3, 5))
    image.fill(_FRAME if not full else pygame.Color("#e83b3b"), (1, 3, 1, 3))
    if full:
        image.fill(_HOT, (1, 0, 1, 2))
    return image


class Hud:
    """Draws `HudState`s and keeps the timers for fading parts."""

    def __init__(self) -> None:
        self._pips = {True: _pip(True), False: _pip(False)}
        self._flares = {True: _flare(True), False: _flare(False)}
        self._font: pygame.font.Font | None = None
        self.clock = 0.0
        self.embers_left = 0.0
        self.embers: int | None = None
        self.banner_text = ""
        self.banner_left = 0.0
        self.hidden = False

    def banner(self, text: str) -> None:
        """Show `text` at the top of the screen for a moment."""
        self.banner_text, self.banner_left = text, BANNER_SHOWN

    def update(self, dt: float) -> None:
        self.clock += dt
        self.embers_left = max(self.embers_left - dt, 0.0)
        self.banner_left = max(self.banner_left - dt, 0.0)

    def draw(self, canvas: pygame.Surface, state: HudState) -> None:
        if state.embers != self.embers:
            if self.embers is not None:
                self.embers_left = EMBERS_SHOWN
            self.embers = state.embers
        if self.hidden:
            return
        x, y = ORIGIN
        for i in range(state.max_health):
            canvas.blit(self._pips[i < state.health], (x + i * (PIP[0] + PIP_GAP), y))
        y += PIP[1] + 3
        right = self._wick(canvas, state, x, y)
        self._flare_icons(canvas, state, right + 5, y - 2)
        if self.embers_left > 0:
            self._embers(canvas, state.embers, x, y + WICK_HEIGHT + 5)
        if self.banner_left > 0:
            self._banner(canvas)

    def _wick(self, canvas: pygame.Surface, state: HudState, x: int, y: int) -> int:
        """The flame bar; returns its right edge."""
        width = max(round(state.max_flame * WICK_PER_FLAME), 8)
        canvas.fill(_INK, (x - 1, y - 1, width + 2, WICK_HEIGHT + 2))
        fraction = max(min(state.flame / state.max_flame, 1.0), 0.0) if state.max_flame else 0.0
        if fraction <= 0:
            if math.sin(self.clock * 10) > 0:
                pygame.draw.rect(canvas, _COOL, (x - 1, y - 1, width + 2, WICK_HEIGHT + 2), 1)
            return x + width
        color = _HOT if fraction > LOW else _COOL.lerp(_WARM, (math.sin(self.clock * 8) + 1) / 2)
        filled = max(round(width * fraction), 1)
        canvas.fill(color, (x, y, filled, WICK_HEIGHT))
        canvas.fill(_CORE, (x + filled - 1, y, 1, WICK_HEIGHT))
        return x + width

    def _flare_icons(self, canvas: pygame.Surface, state: HudState, x: int, y: int) -> None:
        for i in range(state.max_flares):
            full = i < state.flares
            canvas.blit(self._flares[full], (x + i * 5, y))
            if i == state.flares and state.refill > 0:
                height = round(5 * state.refill)
                canvas.fill(_WARM, (x + i * 5 + 1, y + 7 - height, 1, height))

    def _embers(self, canvas: pygame.Surface, count: int, x: int, y: int) -> None:
        font = self._get_font()
        alpha = round(255 * min(self.embers_left / FADE, 1.0))
        gem = [(x + 3, y), (x + 6, y + 4), (x + 3, y + 8), (x, y + 4)]
        pygame.draw.polygon(canvas, _WARM, gem)
        pygame.draw.polygon(canvas, _HOT, [(x + 3, y + 1), (x + 5, y + 4), (x + 3, y + 4)])
        text = font.render(str(count), False, _MIST)
        text.set_alpha(alpha)
        canvas.blit(text, (x + 10, y - 1))

    def _banner(self, canvas: pygame.Surface) -> None:
        font = self._get_font()
        shown = BANNER_SHOWN - self.banner_left
        alpha = min(shown / FADE, self.banner_left / FADE, 1.0)
        text = font.render(self.banner_text, False, _MIST)
        text.set_alpha(round(255 * alpha))
        rect = text.get_rect(midtop=(canvas.get_width() // 2, 28))
        line = pygame.Surface((rect.width + 24, 1), pygame.SRCALPHA)
        line.fill((*_HOT[:3], round(160 * alpha)))
        canvas.blit(text, rect)
        canvas.blit(line, (rect.x - 12, rect.bottom + 2))

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.Font(None, 16)
        return self._font
