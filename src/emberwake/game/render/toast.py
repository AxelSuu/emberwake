"""Short messages in the corner of the screen, such as an achievement unlocking."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from emberwake.game import palette

DURATION = 3.0
MAX_SHOWN = 3
FADE = 0.5


@dataclass(slots=True)
class _Toast:
    text: str
    left: float = DURATION


class Toasts:
    """A queue of messages, newest at the bottom, each shown for `DURATION` seconds."""

    def __init__(self) -> None:
        self._items: list[_Toast] = []
        self._font: pygame.font.Font | None = None

    def __len__(self) -> int:
        return len(self._items)

    def push(self, text: str) -> None:
        """Show `text`; the oldest message goes if too many are showing."""
        self._items.append(_Toast(text))
        del self._items[:-MAX_SHOWN]

    def update(self, dt: float) -> None:
        """Age the messages and drop the expired ones."""
        for item in self._items:
            item.left -= dt
        self._items = [item for item in self._items if item.left > 0]

    def draw(self, canvas: pygame.Surface) -> None:
        """Draw the messages in the top right corner."""
        if not self._items:
            return
        font = self._font = self._font or pygame.font.Font(None, 16)
        y = 6
        for item in self._items:
            image = font.render(item.text, False, palette.EMBER_CORE)
            image.set_alpha(round(255 * min(1.0, item.left / FADE)))
            x = canvas.get_width() - image.get_width() - 8
            canvas.fill(palette.INK, (x - 3, y - 2, image.get_width() + 6, image.get_height() + 4))
            canvas.blit(image, (x, y))
            y += image.get_height() + 6
