"""Areas: rooms grouped by the level field Area, their music and how lit each one is.

An area's light % counts the things in its rooms that ``[light]`` in content/areas.toml lists,
by prefab, with the persisted ``Component.field`` that is true once one is lit. Values come from
the `WorldState` and, for entities never saved, the level files, so unloaded rooms count too.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import SerdeError, from_data
from emberwake.engine.ecs import COMPONENTS
from emberwake.engine.ecs.prefabs import build
from emberwake.engine.world.spawning import prefab_name

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from emberwake.engine.ecs import Registry
    from emberwake.engine.ecs.prefabs import Prefab
    from emberwake.engine.world.ldtk import Level
    from emberwake.engine.world.spawning import WorldState

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


@dataclass(frozen=True, slots=True)
class Light:
    lit: int = 0
    total: int = 0

    @property
    def fraction(self) -> float:
        """0 to 1; an area with nothing to light counts as fully lit."""
        return self.lit / self.total if self.total else 1.0

    @property
    def percent(self) -> int:
        """Rounded down, so 100 means everything."""
        return self.lit * 100 // self.total if self.total else 100


@dataclass(frozen=True, slots=True)
class _Counted:
    area: str
    iid: str
    component: str
    field: str
    initial: bool
    """Lit as placed in the level file."""


class LightCensus:
    """What counts toward each area's light, read once from the level files."""

    def __init__(
        self,
        levels: Iterable[Level],
        prefabs: Mapping[str, Prefab],
        rules: Mapping[str, str],
        registry: Registry = COMPONENTS,
    ) -> None:
        self.areas: list[str] = []
        self._counted: list[_Counted] = []
        for level in levels:
            area = area_of(level)
            if area not in self.areas:
                self.areas.append(area)
            for entity in level.entities():
                name = prefab_name(entity.identifier)
                rule, prefab = rules.get(name), prefabs.get(name)
                if rule is None or prefab is None:
                    continue
                component, _, attribute = rule.partition(".")
                try:
                    placed = build(prefab, entity.values(), registry).get(component)
                except (KeyError, SerdeError):
                    continue
                initial = bool(getattr(placed, attribute, False))
                self._counted.append(_Counted(area, entity.iid, component, attribute, initial))

    def count(self, state: WorldState) -> dict[str, Light]:
        """Each area's light now; every area with rooms is in it."""
        tally = {area: [0, 0] for area in self.areas}
        for counted in self._counted:
            saved = state.entities.get(counted.iid, {}).get(counted.component, {})
            lit = bool(saved.get(counted.field, counted.initial))
            tally[counted.area][0] += lit
            tally[counted.area][1] += 1
        return {area: Light(lit, total) for area, (lit, total) in tally.items()}
