"""Everything that shapes how the game feels, loaded from content/feel.toml (F5 reloads it)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import from_data, to_data
from emberwake.engine.render.camera import CameraTuning
from emberwake.game.breakables import BreakTuning
from emberwake.game.enemies import EnemyTuning
from emberwake.game.lamprey import LampreyTuning
from emberwake.game.lamps import LampTuning
from emberwake.game.light import LightTuning
from emberwake.game.player.swing import SwingTuning
from emberwake.game.player.tuning import PlayerTuning
from emberwake.game.rooms import RoomTuning
from emberwake.game.switches import SwitchTuning

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class JuiceTuning:
    dash_hitstop: int = 3
    death_hitstop: int = 8
    respawn_delay: int = 24
    dash_trauma: float = 0.25
    wall_jump_trauma: float = 0.1
    death_trauma: float = 0.6
    hard_landing: float = 0.85
    """Fraction of max fall speed above which a landing shakes the screen."""
    hard_landing_trauma: float = 0.3
    squash: float = 0.35
    stretch: float = 0.3
    squash_recovery: float = 14.0
    beacon_trauma: float = 0.35
    beacon_flash: float = 0.35
    """Seconds the screen flash lasts when a beacon is relit."""


@dataclass(frozen=True, slots=True)
class Feel:
    player: PlayerTuning = field(default_factory=PlayerTuning)
    camera: CameraTuning = field(default_factory=CameraTuning)
    juice: JuiceTuning = field(default_factory=JuiceTuning)
    rooms: RoomTuning = field(default_factory=RoomTuning)
    light: LightTuning = field(default_factory=LightTuning)
    lamps: LampTuning = field(default_factory=LampTuning)
    enemies: EnemyTuning = field(default_factory=EnemyTuning)
    swing: SwingTuning = field(default_factory=SwingTuning)
    breakables: BreakTuning = field(default_factory=BreakTuning)
    switches: SwitchTuning = field(default_factory=SwitchTuning)
    lamprey: LampreyTuning = field(default_factory=LampreyTuning)


def load_feel(path: Path) -> Feel:
    """Parse `path`. Raises `tomllib.TOMLDecodeError` or `SerdeError` on bad input."""
    return from_data(Feel, tomllib.loads(path.read_text(encoding="utf-8")))


def diff(old: Feel, new: Feel) -> dict[str, tuple[object, object]]:
    """Changed values as ``{"player.max_run": (180.0, 200.0)}``."""
    changes: dict[str, tuple[object, object]] = {}

    def walk(a: object, b: object, path: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for key in a.keys() | b.keys():
                walk(a.get(key), b.get(key), f"{path}.{key}" if path else key)
        elif a != b:
            changes[path] = (a, b)

    walk(to_data(old), to_data(new), "")
    return changes
