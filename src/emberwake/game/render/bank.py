"""Finished sprites by name, compiled from ``art/sprites`` by ``just art`` (ADR 0010).

Gameplay names what it shows (``clockrat``, ``beacon_lit``); the bank answers with the sheet
``assets/sprites/<name>.png`` if there is one, and ``None`` otherwise, so the placeholder art
stands in until the real sprite exists. Multi-frame sheets loop on their own timings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Sheet:
    """A row of equally sized frames and how long each shows, in ms."""

    frames: list[pygame.Surface]
    ms: list[int]

    def at(self, seconds: float) -> pygame.Surface:
        """The frame showing `seconds` into a loop of the sheet."""
        if len(self.frames) == 1:
            return self.frames[0]
        total = sum(self.ms) or len(self.ms)
        t = (seconds * 1000) % total
        for frame, ms in zip(self.frames, self.ms, strict=True):
            if t < ms:
                return frame
            t -= ms
        return self.frames[-1]


class SpriteBank:
    """Loads sheets from `root` on first use; missing names are remembered as missing."""

    def __init__(self, root: Path | None) -> None:
        self.root = root
        self._sheets: dict[str, Sheet | None] = {}

    def sheet(self, name: str) -> Sheet | None:
        """The sheet called `name`, or ``None`` if there is none."""
        if name not in self._sheets:
            self._sheets[name] = self._load(name)
        return self._sheets[name]

    def image(self, name: str, seconds: float = 0.0) -> pygame.Surface | None:
        """The frame of `name` showing at `seconds`, or ``None``."""
        sheet = self.sheet(name)
        return sheet.at(seconds) if sheet is not None else None

    def reload(self) -> None:
        """Forget what was loaded, so recompiled art shows up (F5)."""
        self._sheets.clear()

    def _load(self, name: str) -> Sheet | None:
        if self.root is None:
            return None
        path = self.root / f"{name}.png"
        if not path.is_file():
            return None
        try:
            image = pygame.image.load(path).convert_alpha()
            meta = path.with_suffix(".json")
            info = json.loads(meta.read_text()) if meta.is_file() else {}
        except (pygame.error, OSError, ValueError) as error:
            log.error("Could not load sprite %s: %s", path, error)
            return None
        width, height = info.get("frame", image.get_size())
        count = max(image.get_width() // max(width, 1), 1)
        frames = [image.subsurface((i * width, 0, width, height)) for i in range(count)]
        ms = list(info.get("ms", [100] * count))[:count]
        ms += [100] * (count - len(ms))
        return Sheet(frames, [m if m > 0 else 100 for m in ms])
