"""Areas: rooms grouped by the level field Area, with their music, from content/areas.toml."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.engine.world.ldtk import Level

DEFAULT_AREA = "quarter"
NAME = re.compile(r"[a-z][a-z0-9_]*")
"""What area and stem-set names look like."""


@dataclass(slots=True)
class AreaSpec:
    music: str = ""
    """Stem set of the area's rooms whose Music field is empty."""


@dataclass(slots=True)
class Areas:
    areas: dict[str, AreaSpec] = field(default_factory=dict)
    light: dict[str, str] = field(default_factory=dict)
    """Prefab -> the persisted ``Component.field`` that is true once it is lit."""
    dim: float = 0.7
    """Share of the grade's saturation kept at 0 % light."""
    rate: float = 0.5
    """Light per second the saturation eases by."""


def load_areas(path: Path) -> Areas:
    return from_data(Areas, tomllib.loads(path.read_text(encoding="utf-8")))


def area_of(level: Level) -> str:
    return level.field("Area") or DEFAULT_AREA


def music_of(level: Level, areas: Areas) -> str:
    """The stem set `level` plays: its own, else its area's; empty for silence."""
    if music := level.field("Music"):
        return music
    spec = areas.areas.get(area_of(level))
    return spec.music if spec is not None else ""
