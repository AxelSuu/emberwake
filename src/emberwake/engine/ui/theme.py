"""Widget look: colors, spacing and tween speed, loaded from TOML."""

from __future__ import annotations

import functools
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path


@functools.cache
def _color(value: str) -> pygame.Color:
    return pygame.Color(value)


@dataclass(slots=True)
class Theme:
    """Everything widgets need to draw themselves. Colors are hex strings; sizes are px.

    Attributes:
        font_size: Height of the default pygame font.
        text: Normal text. `dim`: disabled or secondary text. `accent`: focus and fills.
        panel: Panel background. `border`: panel and bar outlines. `focus`: focused row fill.
        pad: Space inside panels. `gap`: space between rows. `row`: minimum row height.
        tween: How fast focus highlights ease, per second (higher is snappier).
    """

    font_size: int = 16
    text: str = "#c7dcd0"
    dim: str = "#7f708a"
    accent: str = "#f9c22b"
    panel: str = "#2e222f"
    border: str = "#625565"
    focus: str = "#45293f"
    pad: int = 6
    gap: int = 2
    row: int = 14
    tween: float = 16.0

    def color(self, name: str) -> pygame.Color:
        """The color field called `name`."""
        return _color(getattr(self, name))

    def font(self) -> pygame.font.Font:
        """The shared font, created on first use (pygame's font module must be initialised)."""
        return _font(self.font_size)

    def render(self, text: str, color: str = "text") -> pygame.Surface:
        """`text` drawn in the color field `color`."""
        return _render(self.font_size, text, getattr(self, color))


@functools.cache
def _font(size: int) -> pygame.font.Font:
    return pygame.font.Font(None, size)


@functools.lru_cache(maxsize=512)
def _render(size: int, text: str, color: str) -> pygame.Surface:
    return _font(size).render(text, False, _color(color))


def load_theme(path: Path) -> Theme:
    """Parse a TOML theme. Raises `tomllib.TOMLDecodeError` or `SerdeError` on bad input."""
    return from_data(Theme, tomllib.loads(path.read_text(encoding="utf-8")))
