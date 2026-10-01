"""Pooled floating text (damage numbers, pickups) that rises, eases out and fades."""

from __future__ import annotations

import pygame

FADE_FROM = 0.5
"""Fraction of a text's life after which it starts to fade."""
CACHE_LIMIT = 64


def ease_out(t: float) -> float:
    """Cubic ease out: fast at first, settling at 1."""
    return 1.0 - (1.0 - t) ** 3


class FloatingTexts:
    """Up to `capacity` live texts in preallocated slots; extra spawns are dropped.

    Rendered text surfaces are cached by text and color, so a repeated "+1" costs one render.

    Args:
        capacity: Most texts alive at once.
        font: Font used for every text. Defaults to pygame's default font at 16 px, created on
            first use because the font module must be initialised first.
    """

    def __init__(self, capacity: int = 32, font: pygame.font.Font | None = None) -> None:
        self.capacity = capacity
        self._font = font
        self.count = 0
        self.dropped = 0
        """Texts refused for lack of room since the start."""
        self.muted = False
        """Reduce-flashes setting: texts still show but do not pop (no rise tween)."""
        self._text = [""] * capacity
        self._color = [(255, 255, 255)] * capacity
        self._x = [0.0] * capacity
        self._y = [0.0] * capacity
        self._rise = [0.0] * capacity
        self._age = [0.0] * capacity
        self._life = [0.0] * capacity
        self._images: dict[tuple[str, tuple[int, int, int]], pygame.Surface] = {}

    def spawn(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple[int, int, int] = (255, 255, 255),
        *,
        rise: float = 20.0,
        life: float = 0.8,
    ) -> None:
        """Show `text` centred on world position `(x, y)`, rising `rise` px over `life` s."""
        if self.count == self.capacity:
            self.dropped += 1
            return
        i = self.count
        self._text[i], self._color[i] = text, color
        self._x[i], self._y[i] = x, y
        self._rise[i], self._age[i], self._life[i] = rise, 0.0, life
        self.count += 1

    def update(self, dt: float) -> None:
        """Age every text and retire the finished ones."""
        i = 0
        while i < self.count:
            self._age[i] += dt
            if self._age[i] >= self._life[i]:
                self._remove(i)
            else:
                i += 1

    def draw(self, canvas: pygame.Surface, offset: tuple[int, int]) -> None:
        """Draw every text; `offset` is the camera's world position."""
        ox, oy = offset
        for i in range(self.count):
            t = self._age[i] / self._life[i]
            image = self._image(self._text[i], self._color[i])
            lift = self._rise[i] * (1.0 if self.muted else ease_out(t))
            alpha = 255 if t < FADE_FROM else round(255 * (1.0 - (t - FADE_FROM) / (1 - FADE_FROM)))
            image.set_alpha(alpha)
            rect = image.get_rect(center=(round(self._x[i]) - ox, round(self._y[i] - lift) - oy))
            canvas.blit(image, rect)

    def clear(self) -> None:
        """Remove every text."""
        self.count = 0

    def _remove(self, i: int) -> None:
        last = self.count - 1
        if i != last:
            self._text[i], self._color[i] = self._text[last], self._color[last]
            self._x[i], self._y[i] = self._x[last], self._y[last]
            self._rise[i], self._age[i] = self._rise[last], self._age[last]
            self._life[i] = self._life[last]
        self.count = last

    def _image(self, text: str, color: tuple[int, int, int]) -> pygame.Surface:
        key = (text, color)
        image = self._images.get(key)
        if image is None:
            if len(self._images) >= CACHE_LIMIT:
                self._images.clear()
            font = self._font or pygame.font.Font(None, 16)
            self._font = font
            glyphs = font.render(text, False, color)
            image = pygame.Surface(glyphs.get_size(), pygame.SRCALPHA)
            image.blit(glyphs, (0, 0))
            self._images[key] = image
        return image
