"""Large static images split into square chunks, baked lazily and drawn with ``fblits``."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

CHUNK = 256

type Paint = Callable[[pygame.Surface, pygame.Rect], None]
"""Draws `area` (in layer pixels) into a surface whose top-left is ``area.topleft``."""


class ChunkLayer:
    """A static image of `size` px placed at world `origin`, painted one chunk at a time.

    `bake` yields after every chunk so the work can be spread across frames (`Jobs`). `draw`
    bakes any visible chunk that is still missing, so the picture is never incomplete.
    """

    def __init__(
        self, origin: tuple[int, int], size: tuple[int, int], paint: Paint, chunk: int = CHUNK
    ) -> None:
        self.origin = origin
        self.size = size
        self.paint = paint
        self.chunk = chunk
        self.columns = math.ceil(size[0] / chunk)
        self.rows = math.ceil(size[1] / chunk)
        self._chunks: dict[tuple[int, int], pygame.Surface] = {}

    @property
    def baked(self) -> int:
        """How many chunks are baked."""
        return len(self._chunks)

    @property
    def total(self) -> int:
        """How many chunks the layer has."""
        return self.columns * self.rows

    def bake(self) -> Iterator[None]:
        """Bake missing chunks row by row, yielding after each one."""
        for row in range(self.rows):
            for column in range(self.columns):
                if (column, row) not in self._chunks:
                    self._bake(column, row)
                    yield

    def draw(self, target: pygame.Surface, offset: tuple[int, int]) -> None:
        """Draw the chunks overlapping `target`, whose top-left is at world `offset`."""
        x = offset[0] - self.origin[0]
        y = offset[1] - self.origin[1]
        width, height = target.get_size()
        size = self.chunk
        blits = []
        for row in range(max(0, y // size), min(self.rows, (y + height - 1) // size + 1)):
            for column in range(max(0, x // size), min(self.columns, (x + width - 1) // size + 1)):
                image = self._chunks.get((column, row))
                if image is None:
                    image = self._bake(column, row)
                blits.append((image, (column * size - x, row * size - y)))
        target.fblits(blits)

    def _bake(self, column: int, row: int) -> pygame.Surface:
        area = pygame.Rect(column * self.chunk, row * self.chunk, self.chunk, self.chunk)
        area = area.clip(pygame.Rect((0, 0), self.size))
        image = pygame.Surface(area.size, pygame.SRCALPHA)
        if pygame.display.get_surface() is not None:
            image = image.convert_alpha()
        self.paint(image, area)
        self._chunks[column, row] = image
        return image
