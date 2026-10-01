"""Find colors that are not in the Resurrect 64 palette.

Checks PNG pixels (anything not fully transparent) and ``#rrggbb`` literals in TOML and in game
code. Engine code is generic and may use any color, so it is not scanned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from emberwake.game.palette import RESURRECT_64

if TYPE_CHECKING:
    from collections.abc import Iterator

PALETTE = frozenset(RESURRECT_64)
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
TEXT_GLOBS = ("content/**/*.toml", "levels/src/*.toml", "src/emberwake/game/**/*.py")
IMAGE_GLOBS = ("assets/**/*.png", "content/**/*.png")


@dataclass(frozen=True, slots=True)
class Offender:
    path: Path
    where: str
    color: str

    def __str__(self) -> str:
        return f"{self.path}:{self.where}: {self.color} is not in the palette"


def lint_text(path: Path) -> Iterator[Offender]:
    """Off-palette hex literals in a text file."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for color in HEX.findall(line):
            if color.lower() not in PALETTE:
                yield Offender(path, str(number), color.lower())


def lint_image(path: Path) -> Iterator[Offender]:
    """Off-palette colors in a PNG, reported once each at their first pixel."""
    image = pygame.image.load(path)
    seen: set[str] = set()
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            r, g, b, a = image.get_at((x, y))
            color = f"#{r:02x}{g:02x}{b:02x}"
            if a and color not in PALETTE and color not in seen:
                seen.add(color)
                yield Offender(path, f"{x},{y}", color)


def lint(root: Path) -> list[Offender]:
    """Every offender under `root`, in path order."""
    found: list[Offender] = []
    for pattern in TEXT_GLOBS:
        for path in sorted(root.glob(pattern)):
            found.extend(lint_text(path))
    for pattern in IMAGE_GLOBS:
        for path in sorted(root.glob(pattern)):
            found.extend(lint_image(path))
    return found
