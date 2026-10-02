"""Speech bubbles: a few wrapped lines of text above a point in the world."""

from __future__ import annotations

import pygame

from emberwake.game import palette

WIDTH = 150
"""Widest a line of text may be, in px."""
PAD = 4
GAP = 4
"""Space between the bubble and the point it speaks from."""


class Bubbles:
    """Draws speech with a small font, caching what it has rendered."""

    def __init__(self) -> None:
        self._font: pygame.font.Font | None = None
        self._cache: dict[str, pygame.Surface] = {}

    def draw(self, canvas: pygame.Surface, text: str, midbottom: tuple[float, float]) -> None:
        """Draw `text` centred above `midbottom` (canvas px), kept on screen."""
        image = self._image(text)
        rect = image.get_rect(midbottom=(round(midbottom[0]), round(midbottom[1]) - GAP))
        rect.clamp_ip(canvas.get_rect())
        canvas.blit(image, rect)

    def _image(self, text: str) -> pygame.Surface:
        if text not in self._cache:
            font = self._font = self._font or pygame.font.Font(None, 16)
            lines = _wrap(font, text)
            height = font.get_linesize()
            width = max(font.size(line)[0] for line in lines)
            image = pygame.Surface((width + 2 * PAD, height * len(lines) + 2 * PAD))
            image.fill(palette.INK)
            pygame.draw.rect(image, palette.DUSK, image.get_rect(), 1)
            for row, line in enumerate(lines):
                image.blit(font.render(line, False, palette.MIST), (PAD, PAD + row * height))
            self._cache[text] = image
        return self._cache[text]


def _wrap(font: pygame.font.Font, text: str) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}" if line else word
            if line and font.size(trial)[0] > WIDTH:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines
