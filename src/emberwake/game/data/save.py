"""Save slots: progress persisted as ``saves/slot_N.json``, written at beacons and on quit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from emberwake.engine.core.serde import VersionedCodec
from emberwake.engine.platform.documents import load_document, save_document
from emberwake.engine.world.spawning import WorldState
from emberwake.game.grants import START

if TYPE_CHECKING:
    from emberwake.engine.platform.storage import Storage

SLOTS = (1, 2, 3)


@dataclass(slots=True)
class Stats:
    deaths: int = 0
    jumps: int = 0
    dashes: int = 0
    embers: int = 0


@dataclass(slots=True)
class Cinder:
    """Embers dropped where the player died, waiting to be picked up."""

    room: str
    x: float
    y: float
    """World px of the spot."""
    embers: int


@dataclass(slots=True)
class SaveSlot:
    room: str
    """Room to continue in: the last beacon's, or where the game started."""
    beacon: str = ""
    """Iid of the beacon to continue at; empty continues at the room's PlayerStart."""
    playtime: float = 0.0
    """Simulated seconds played."""
    flags: dict[str, int] = field(default_factory=dict)
    world: WorldState = field(default_factory=WorldState)
    discovered: list[str] = field(default_factory=list)
    """Iids of rooms entered, in order."""
    stats: Stats = field(default_factory=Stats)
    cinder: Cinder | None = None
    abilities: list[str] = field(default_factory=lambda: list(START))
    inventory: dict[str, int] = field(default_factory=dict)
    """Item counts: shards, oil flasks, flare pouches, keys."""


def _add_cinder(data: dict[str, Any]) -> dict[str, Any]:
    """v1 -> v2: the dropped-embers spot; none in older saves."""
    return data


def _add_loadout(data: dict[str, Any]) -> dict[str, Any]:
    """v2 -> v3: abilities and items. Older games always had dash and flares."""
    data.setdefault("abilities", ["dash", "flare"])
    data.setdefault("inventory", {})
    return data


SAVE_CODEC = VersionedCodec(SaveSlot, version=3, migrations={1: _add_cinder, 2: _add_loadout})
"""Bump the version and add a migration whenever `SaveSlot` (or what it holds) changes shape."""


def slot_key(slot: int) -> str:
    return f"saves/slot_{slot}.json"


def load_slot(storage: Storage, slot: int) -> SaveSlot | None:
    """The saved progress, or ``None`` if the slot is empty or unreadable (kept as .corrupt)."""
    return load_document(storage, slot_key(slot), SAVE_CODEC, lambda: None)


def save_slot(storage: Storage, slot: int, progress: SaveSlot) -> None:
    save_document(storage, slot_key(slot), SAVE_CODEC, progress)
