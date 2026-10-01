"""Skins and lantern colors, read from ``content/cosmetics.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_SKIN = "default"
DEFAULT_LANTERN = "ember"


@dataclass(slots=True)
class Skin:
    """A palette swap of the player's cloak; empty colors keep the original."""

    cloak: str = ""
    cloak_shade: str = ""
    cloak_dark: str = ""
    eyes: str = ""


@dataclass(slots=True)
class Cosmetics:
    skins: dict[str, Skin] = field(default_factory=dict)
    lanterns: dict[str, str] = field(default_factory=dict)

    def skin(self, name: str) -> Skin:
        """The named skin, or the default one if the name is unknown."""
        return self.skins.get(name) or self.skins.get(DEFAULT_SKIN) or Skin()

    def lantern(self, name: str, fallback: str) -> str:
        """The named lantern color (hex), or `fallback`."""
        return self.lanterns.get(name) or self.lanterns.get(DEFAULT_LANTERN) or fallback


def load_cosmetics(path: Path) -> Cosmetics:
    """Parse the TOML file. Raises `tomllib.TOMLDecodeError` or `SerdeError`."""
    return from_data(Cosmetics, tomllib.loads(path.read_text(encoding="utf-8")))
