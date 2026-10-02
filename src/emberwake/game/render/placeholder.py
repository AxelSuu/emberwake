"""Programmatic placeholder art, so gameplay never waits for real sprites (ADR 0010)."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.noise import ValueNoise
from emberwake.engine.physics import Tile, TileGrid
from emberwake.game import palette

if TYPE_CHECKING:
    from collections.abc import Mapping

    from emberwake.engine.render.chunks import Paint

ROCK = pygame.Color("#3e3546")
ROCK_DARK = pygame.Color("#2e222f")
ROCK_SPECK = pygame.Color("#45293f")
ROCK_EDGE = pygame.Color("#625565")
ROCK_LIGHT = pygame.Color("#7f708a")
PLANK = pygame.Color("#966c6c")
PLANK_LIGHT = pygame.Color("#ab947a")
PLANK_DARK = pygame.Color("#6e2727")
POST = pygame.Color("#694f62")
SPIKE = pygame.Color("#b33831")
SPIKE_TIP = pygame.Color("#f68181")

CLOAK = pygame.Color("#4d65b4")
CLOAK_SHADE = pygame.Color("#484a77")
CLOAK_DARK = pygame.Color("#323353")
EYES = pygame.Color("#8ff8e2")
LANTERN_FRAME = pygame.Color("#625565")

MISSING = pygame.Color("#f04f78")

SPRITE_SIZE = (14, 22)
LANTERN = (12.5, 13.5)
"""Lantern centre in the right-facing sprite, from its top-left."""


def tile_painter(grid: TileGrid) -> Paint:
    """Paints the tiles of `grid` that fall inside a chunk's area."""

    def paint(surface: pygame.Surface, area: pygame.Rect) -> None:
        size = grid.tile_size
        for row in range(area.top // size, math.ceil(area.bottom / size)):
            for column in range(area.left // size, math.ceil(area.right / size)):
                tile = grid.get(column, row)
                rect = pygame.Rect(column * size - area.left, row * size - area.top, size, size)
                if tile is Tile.SOLID:
                    _rock(surface, grid, column, row, rect)
                elif tile is Tile.ONE_WAY:
                    _plank(surface, grid, column, row, rect)
                elif tile is Tile.HAZARD:
                    _spikes(surface, grid, column, row, rect)

    return paint


def _rock(
    surface: pygame.Surface, grid: TileGrid, column: int, row: int, rect: pygame.Rect
) -> None:
    def open_at(dx: int, dy: int) -> bool:
        return grid.get(column + dx, row + dy) is not Tile.SOLID

    surface.fill(ROCK, rect)
    rng = random.Random(column * 7919 + row * 104729)
    for _ in range(3):
        x, y = rng.randrange(1, rect.w - 1), rng.randrange(1, rect.h - 1)
        surface.fill(ROCK_SPECK, (rect.x + x, rect.y + y, rng.choice((1, 2)), 1))
    if open_at(0, 1):
        surface.fill(ROCK_DARK, (rect.x, rect.bottom - 2, rect.w, 2))
    if open_at(-1, 0):
        surface.fill(ROCK_EDGE, (rect.x, rect.y, 1, rect.h))
    if open_at(1, 0):
        surface.fill(ROCK_DARK, (rect.right - 1, rect.y, 1, rect.h))
    if open_at(0, -1):
        surface.fill(ROCK_EDGE, (rect.x, rect.y, rect.w, 3))
        surface.fill(ROCK_LIGHT, (rect.x, rect.y, rect.w, 1))


def _plank(
    surface: pygame.Surface, grid: TileGrid, column: int, row: int, rect: pygame.Rect
) -> None:
    surface.fill(PLANK, (rect.x, rect.y, rect.w, 4))
    surface.fill(PLANK_LIGHT, (rect.x, rect.y, rect.w, 1))
    surface.fill(PLANK_DARK, (rect.x, rect.y + 4, rect.w, 1))
    for side, x in ((-1, rect.x + 2), (1, rect.right - 4)):
        if grid.get(column + side, row) is not Tile.ONE_WAY:
            surface.fill(POST, (x, rect.y + 5, 2, 6))


def _spikes(
    surface: pygame.Surface, grid: TileGrid, column: int, row: int, rect: pygame.Rect
) -> None:
    down = grid.get(column, row - 1) is Tile.SOLID and grid.get(column, row + 1) is not Tile.SOLID
    for i in range(4):
        x = rect.x + i * 4
        if down:
            points = [(x, rect.y), (x + 2, rect.y + 10), (x + 4, rect.y)]
            tip = (x + 2, rect.y + 9)
        else:
            points = [(x, rect.bottom), (x + 2, rect.bottom - 10), (x + 4, rect.bottom)]
            tip = (x + 2, rect.bottom - 10)
        pygame.draw.polygon(surface, SPIKE, points)
        surface.fill(SPIKE_TIP, (*tip, 1, 1))


def _player_image(
    skin: Mapping[str, str] | None = None, flame: str | None = None, *, lantern: bool = True
) -> pygame.Surface:
    """The player; `skin` overrides ``cloak``, ``cloak_shade``, ``cloak_dark`` and ``eyes``.

    Without `lantern` the arm and lantern are left out, for swings that draw them apart.
    """
    skin = skin or {}
    cloak = pygame.Color(skin.get("cloak") or CLOAK)
    shade = pygame.Color(skin.get("cloak_shade") or CLOAK_SHADE)
    dark = pygame.Color(skin.get("cloak_dark") or CLOAK_DARK)
    eyes = pygame.Color(skin.get("eyes") or EYES)
    image = pygame.Surface(SPRITE_SIZE, pygame.SRCALPHA).convert_alpha()
    pygame.draw.polygon(image, cloak, [(4, 6), (9, 6), (12, 21), (1, 21)])
    pygame.draw.polygon(image, shade, [(7, 6), (9, 6), (12, 21), (7, 21)])
    pygame.draw.ellipse(image, cloak, (3, 0, 8, 9))
    image.fill(palette.INK, (5, 3, 4, 4))
    image.fill(eyes, (6, 4, 1, 1))
    image.fill(eyes, (8, 4, 1, 1))
    image.fill(dark, (4, 21, 2, 1))
    image.fill(dark, (8, 21, 2, 1))
    if lantern:
        pygame.draw.line(image, dark, (9, 10), (12, 11))
        image.blit(lantern_image(flame), (11, 11))
    return image


def lantern_image(flame: str | None = None) -> pygame.Surface:
    """The lantern on its own, 3x5 px."""
    glow = pygame.Color(flame or palette.EMBER_HOT)
    core = glow.lerp(pygame.Color(palette.EMBER_CORE), 0.6)
    image = pygame.Surface((3, 5), pygame.SRCALPHA)
    image.fill(LANTERN_FRAME, (0, 0, 3, 1))
    image.fill(glow, (0, 1, 3, 4))
    image.fill(core, (1, 2, 1, 2))
    return image


class PlayerSprite:
    """Player images per facing and squash, cached so nothing is transformed every frame."""

    QUANTUM = 0.05

    def __init__(self, skin: Mapping[str, str] | None = None, flame: str | None = None) -> None:
        right = _player_image(skin, flame)
        bare = _player_image(skin, flame, lantern=False)
        self._base = {
            (1, False): right,
            (-1, False): pygame.transform.flip(right, True, False),
            (1, True): bare,
            (-1, True): pygame.transform.flip(bare, True, False),
        }
        self.lantern = lantern_image(flame)
        self._cache: dict[tuple[int, int, int, bool], pygame.Surface] = {}

    def image(
        self, facing: int, scale_x: float, scale_y: float, *, bare: bool = False
    ) -> pygame.Surface:
        """The player facing `facing`, squashed; `bare` leaves out the lantern."""
        qx, qy = round(scale_x / self.QUANTUM), round(scale_y / self.QUANTUM)
        key = (facing, qx, qy, bare)
        if key not in self._cache:
            base = self._base[facing, bare]
            width, height = base.get_size()
            size = (
                max(round(width * qx * self.QUANTUM), 1),
                max(round(height * qy * self.QUANTUM), 1),
            )
            self._cache[key] = pygame.transform.scale(base, size)
        return self._cache[key]

    @staticmethod
    def lantern_offset(facing: int, scale_x: float, scale_y: float) -> tuple[float, float]:
        """Lantern position relative to the feet (bottom centre of the sprite)."""
        width, height = SPRITE_SIZE
        x = (LANTERN[0] - width / 2) * facing * scale_x
        y = (LANTERN[1] - height) * scale_y
        return x, y


class Flicker:
    """A gentle light flicker between 0.55 and 1."""

    def __init__(self, seed: int = 0) -> None:
        self._noise = ValueNoise(seed)

    def __call__(self, time: float) -> float:
        return 0.55 + 0.45 * (self._noise(time * 6) + 1) / 2


def _prompt() -> pygame.Surface:
    """A small up arrow: press up (or interact) here."""
    image = pygame.Surface((7, 6), pygame.SRCALPHA).convert_alpha()
    arrow = [(3, 0), (6, 3), (4, 3), (4, 5), (2, 5), (2, 3), (0, 3)]
    pygame.draw.polygon(image, palette.MIST, arrow)
    return image


class EntityArt:
    """Placeholder images for `Sprite` names, sized to the entity's body and cached."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self.prompt = _prompt()

    def image(self, name: str, size: tuple[int, int]) -> pygame.Surface:
        key = (name, *size)
        if key not in self._cache:
            image = pygame.Surface(size, pygame.SRCALPHA).convert_alpha()
            painter = getattr(self, f"_{name}", None)
            if painter is None:
                pygame.draw.rect(image, MISSING, image.get_rect(), 1)
            else:
                painter(image, image.get_rect())
            self._cache[key] = image
        return self._cache[key]

    @staticmethod
    def _door(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(PLANK_DARK, rect)
        image.fill(PLANK, rect.inflate(-4, -2))
        for y in range(rect.top + 6, rect.bottom - 2, 8):
            image.fill(PLANK_DARK, (rect.left + 2, y, rect.width - 4, 1))
        image.fill(LANTERN_FRAME, (rect.right - 5, rect.centery - 1, 2, 3))

    @staticmethod
    def _lever(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(ROCK_EDGE, (rect.centerx - 4, rect.bottom - 3, 8, 3))
        base, tip = (rect.centerx, rect.bottom - 3), (rect.centerx + 4, rect.top + 5)
        pygame.draw.line(image, POST, base, tip, 2)
        image.fill(palette.EMBER_WARM, (rect.centerx + 3, rect.top + 3, 3, 3))

    @staticmethod
    def _plate(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(ROCK_EDGE, (rect.left + 1, rect.bottom - 3, rect.width - 2, 3))
        image.fill(PLANK_LIGHT, (rect.left + 2, rect.bottom - 4, rect.width - 4, 1))

    @staticmethod
    def _beacon(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(ROCK_EDGE, (rect.centerx - 3, rect.top + 6, 6, rect.height - 6))
        image.fill(ROCK_LIGHT, (rect.centerx - 3, rect.top + 6, 1, rect.height - 6))
        image.fill(LANTERN_FRAME, (rect.centerx - 4, rect.top + 4, 8, 2))
        image.fill(palette.EMBER_COOL, (rect.centerx - 2, rect.top + 1, 4, 3))

    @staticmethod
    def _beacon_lit(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(ROCK_EDGE, (rect.centerx - 3, rect.top + 6, 6, rect.height - 6))
        image.fill(ROCK_LIGHT, (rect.centerx - 3, rect.top + 6, 1, rect.height - 6))
        image.fill(LANTERN_FRAME, (rect.centerx - 4, rect.top + 4, 8, 2))
        image.fill(palette.EMBER_WARM, (rect.centerx - 3, rect.top, 6, 4))
        image.fill(palette.EMBER_CORE, (rect.centerx - 1, rect.top + 1, 2, 3))

    @staticmethod
    def _lightform(image: pygame.Surface, rect: pygame.Rect) -> None:
        for x in range(rect.left, rect.right, 4):
            image.fill(ROCK_EDGE, (x, rect.top, 2, 1))
            image.fill(ROCK_EDGE, (x, rect.bottom - 1, 2, 1))

    @staticmethod
    def _lightform_lit(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(palette.EMBER_WARM, (rect.left, rect.top, rect.width, 3))
        image.fill(palette.EMBER_CORE, (rect.left, rect.top, rect.width, 1))

    @staticmethod
    def _cracked_wall(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(ROCK_EDGE, rect)
        image.fill(ROCK, rect.inflate(-2, -2))
        for y in range(rect.top, rect.bottom, 16):
            x = rect.centerx
            for step in range(0, min(16, rect.bottom - y), 4):
                x += (-2, 2)[step // 4 % 2]
                image.fill(ROCK_DARK, (x, y + step, 2, 4))

    @staticmethod
    def _crate(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(PLANK_DARK, rect)
        image.fill(PLANK, rect.inflate(-2, -2))
        right, bottom = rect.right - 1, rect.bottom - 1
        pygame.draw.line(image, PLANK_DARK, rect.topleft, (right, bottom))
        pygame.draw.line(image, PLANK_DARK, (right, rect.top), (rect.left, bottom))
        image.fill(PLANK_LIGHT, (rect.left + 1, rect.top + 1, rect.width - 2, 1))

    @staticmethod
    def _pot(image: pygame.Surface, rect: pygame.Rect) -> None:
        w, h = rect.size
        pygame.draw.ellipse(image, PLANK_DARK, (1, 3, w - 2, h - 3))
        pygame.draw.ellipse(image, PLANK, (2, 4, w - 5, h - 6))
        image.fill(PLANK_DARK, (w // 2 - 3, 1, 6, 3))
        image.fill(PLANK_LIGHT, (4, 6, 2, 3))

    @staticmethod
    def _crumbling_platform(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(PLANK_DARK, (rect.left, rect.top, rect.width, 5))
        image.fill(PLANK, (rect.left, rect.top, rect.width, 4))
        image.fill(PLANK_LIGHT, (rect.left, rect.top, rect.width, 1))
        for x in range(rect.left + 5, rect.right - 2, 9):
            image.fill(PLANK_DARK, (x, rect.top + 1, 1, 3))

    @staticmethod
    def _crumbling_platform_gone(image: pygame.Surface, rect: pygame.Rect) -> None:
        for x in range(rect.left, rect.right, 4):
            image.fill(PLANK_DARK, (x, rect.top, 2, 1))

    @staticmethod
    def _brazier(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(LANTERN_FRAME, (rect.centerx - 5, rect.bottom - 6, 10, 2))
        image.fill(ROCK_EDGE, (rect.centerx - 3, rect.bottom - 4, 6, 4))
        image.fill(palette.EMBER_WARM, (rect.centerx - 3, rect.bottom - 10, 6, 4))
        image.fill(palette.EMBER_CORE, (rect.centerx - 1, rect.bottom - 9, 2, 3))

    @staticmethod
    def _clockrat(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(PLANK_DARK, (rect.left + 1, rect.bottom - 7, rect.width - 2, 6))
        image.fill(PLANK_LIGHT, (rect.left + 2, rect.bottom - 8, rect.width - 6, 2))
        image.fill(SPIKE_TIP, (rect.right - 4, rect.bottom - 6, 2, 2))
        image.fill(ROCK_EDGE, (rect.left + 2, rect.bottom - 1, 2, 1))
        image.fill(ROCK_EDGE, (rect.right - 5, rect.bottom - 1, 2, 1))

    @staticmethod
    def _gloomcrawler(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(CLOAK_DARK, (rect.left, rect.bottom - 6, rect.width, 5))
        image.fill(CLOAK_SHADE, (rect.left + 2, rect.bottom - 7, rect.width - 4, 2))
        image.fill(EYES, (rect.right - 5, rect.bottom - 5, 2, 1))
        image.fill(EYES, (rect.right - 9, rect.bottom - 5, 2, 1))

    @staticmethod
    def _wisp_eater(image: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.circle(image, CLOAK_SHADE, rect.center, rect.width // 2 - 1)
        pygame.draw.circle(image, CLOAK_DARK, rect.center, rect.width // 2 - 3)
        image.fill(EYES, (rect.centerx - 2, rect.centery - 1, 4, 2))

    @staticmethod
    def _flare(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(palette.EMBER_WARM, rect)
        image.fill(palette.EMBER_CORE, rect.inflate(-2, -2))

    @staticmethod
    def _tinker(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(PLANK_DARK, (rect.centerx - 4, rect.bottom - 11, 8, 11))
        image.fill(PLANK, (rect.centerx - 3, rect.bottom - 10, 6, 9))
        pygame.draw.circle(image, PLANK_LIGHT, (rect.centerx, rect.bottom - 13), 3)
        image.fill(LANTERN_FRAME, (rect.centerx - 5, rect.bottom - 16, 10, 2))
        image.fill(palette.EMBER_HOT, (rect.centerx + 4, rect.bottom - 8, 2, 3))

    @staticmethod
    def _goal(image: pygame.Surface, rect: pygame.Rect) -> None:
        for y in range(rect.top, rect.bottom, 8):
            image.fill(palette.EMBER_CORE, (rect.left + 2, y, 3, 4))
            image.fill(palette.MIST, (rect.left + 5, y + 4, 3, 4))
        image.fill(palette.EMBER_HOT, (rect.left, rect.top, 2, rect.height))

    @staticmethod
    def _grant(image: pygame.Surface, rect: pygame.Rect) -> None:
        """A small pedestal holding a glowing orb."""
        w, h = rect.size
        image.fill(ROCK_EDGE, (2, h - 4, w - 4, 4))
        image.fill(ROCK_LIGHT, (2, h - 4, w - 4, 1))
        pygame.draw.circle(image, palette.EMBER_WARM, (w // 2, h - 9), 4)
        pygame.draw.circle(image, palette.EMBER_HOT, (w // 2, h - 9), 3)
        image.fill(palette.EMBER_CORE, (w // 2 - 1, h - 11, 2, 2))

    @staticmethod
    def _cinder(image: pygame.Surface, rect: pygame.Rect) -> None:
        """A small heap of embers, glowing."""
        w, h = rect.size
        pygame.draw.ellipse(image, palette.INK, (0, h - 5, w, 5))
        for i, color in enumerate((palette.EMBER_COOL, palette.EMBER_WARM, palette.EMBER_HOT)):
            pygame.draw.ellipse(image, color, (2 + i, h - 6 - i * 2, w - 4 - 2 * i, 4))
        image.fill(palette.EMBER_CORE, (w // 2 - 1, h - 9, 2, 2))

    @staticmethod
    def _ember(image: pygame.Surface, rect: pygame.Rect) -> None:
        cx, cy = rect.center
        diamond = [(cx, cy - 4), (cx + 3, cy), (cx, cy + 4), (cx - 3, cy)]
        pygame.draw.polygon(image, palette.EMBER_WARM, diamond)
        image.fill(palette.EMBER_CORE, (cx - 1, cy - 1, 2, 2))

    @staticmethod
    def _door_open(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(PLANK_DARK, (rect.left, rect.top, rect.width, 2))
        image.fill(PLANK_DARK, (rect.left, rect.top, 2, rect.height))
        image.fill(PLANK_DARK, (rect.right - 2, rect.top, 2, rect.height))

    @staticmethod
    def _lever_on(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(ROCK_EDGE, (rect.centerx - 4, rect.bottom - 3, 8, 3))
        base, tip = (rect.centerx, rect.bottom - 3), (rect.centerx - 4, rect.top + 5)
        pygame.draw.line(image, POST, base, tip, 2)
        image.fill(palette.EMBER_HOT, (rect.centerx - 6, rect.top + 3, 3, 3))

    @staticmethod
    def _plate_down(image: pygame.Surface, rect: pygame.Rect) -> None:
        image.fill(ROCK_EDGE, (rect.left + 1, rect.bottom - 2, rect.width - 2, 2))
        image.fill(palette.EMBER_HOT, (rect.left + 2, rect.bottom - 3, rect.width - 4, 1))
