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


def _player_image() -> pygame.Surface:
    image = pygame.Surface(SPRITE_SIZE, pygame.SRCALPHA).convert_alpha()
    pygame.draw.polygon(image, CLOAK, [(4, 6), (9, 6), (12, 21), (1, 21)])
    pygame.draw.polygon(image, CLOAK_SHADE, [(7, 6), (9, 6), (12, 21), (7, 21)])
    pygame.draw.ellipse(image, CLOAK, (3, 0, 8, 9))
    image.fill(palette.INK, (5, 3, 4, 4))
    image.fill(EYES, (6, 4, 1, 1))
    image.fill(EYES, (8, 4, 1, 1))
    image.fill(CLOAK_DARK, (4, 21, 2, 1))
    image.fill(CLOAK_DARK, (8, 21, 2, 1))
    pygame.draw.line(image, CLOAK_DARK, (9, 10), (12, 11))
    image.fill(LANTERN_FRAME, (11, 11, 3, 1))
    image.fill(palette.EMBER_HOT, (11, 12, 3, 4))
    image.fill(palette.EMBER_CORE, (12, 13, 1, 2))
    return image


class PlayerSprite:
    """Player images per facing and squash, cached so nothing is transformed every frame."""

    QUANTUM = 0.05

    def __init__(self) -> None:
        right = _player_image()
        self._base = {1: right, -1: pygame.transform.flip(right, True, False)}
        self._cache: dict[tuple[int, int, int], pygame.Surface] = {}

    def image(self, facing: int, scale_x: float, scale_y: float) -> pygame.Surface:
        qx, qy = round(scale_x / self.QUANTUM), round(scale_y / self.QUANTUM)
        key = (facing, qx, qy)
        if key not in self._cache:
            base = self._base[facing]
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
