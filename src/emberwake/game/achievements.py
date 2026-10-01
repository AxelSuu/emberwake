"""Event-driven achievements, kept across save slots in ``achievements.json``.

Gameplay reports events (`record`) and rooms entered (`enter_room`); achievements defined in
``content/achievements.toml`` unlock when a counter reaches its target. An unlock is saved at
once, so quitting never loses one.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import VersionedCodec, from_data
from emberwake.engine.platform.documents import load_document, save_document

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from emberwake.engine.platform.storage import Storage

log = logging.getLogger(__name__)

ACHIEVEMENTS_KEY = "achievements.json"


@dataclass(slots=True)
class Def:
    """One achievement: reach `count` of an event, or enter `rooms` distinct rooms."""

    event: str = ""
    """Counter name: an event class such as ``Jumped``, ``Dashed``, ``Collected`` (embers)."""
    count: int = 1
    rooms: int = 0
    """If set, unlock on entering this many different rooms instead of counting an event."""

    @property
    def target(self) -> int:
        return self.rooms or self.count


@dataclass(slots=True)
class AchievementData:
    counters: dict[str, int] = field(default_factory=dict)
    unlocked: list[str] = field(default_factory=list)
    """Ids in the order they were earned."""
    rooms: list[str] = field(default_factory=list)
    """Distinct rooms ever entered."""


ACHIEVEMENTS_CODEC = VersionedCodec(AchievementData, version=1)
"""Bump the version and add a migration whenever `AchievementData` changes shape."""


def load_defs(path: Path) -> dict[str, Def]:
    """Parse a TOML file of achievements. Raises `tomllib.TOMLDecodeError` or `SerdeError`."""
    return from_data(dict[str, Def], tomllib.loads(path.read_text(encoding="utf-8")))


class Achievements:
    """Counts events and unlocks achievements.

    Args:
        defs: The achievements by id.
        data: Saved progress; a fresh one if omitted.
        storage: Where to save unlocks; nothing is saved without it.
        on_unlock: Called with the id of each new unlock.
    """

    def __init__(
        self,
        defs: dict[str, Def] | None = None,
        data: AchievementData | None = None,
        storage: Storage | None = None,
        on_unlock: Callable[[str], None] | None = None,
    ) -> None:
        self.defs = defs or {}
        self.data = data or AchievementData()
        self.storage = storage
        self.on_unlock = on_unlock

    @classmethod
    def load(
        cls, defs: dict[str, Def], storage: Storage, on_unlock: Callable[[str], None] | None = None
    ) -> Achievements:
        """Achievements with progress read from `storage`."""
        data = load_document(storage, ACHIEVEMENTS_KEY, ACHIEVEMENTS_CODEC, AchievementData)
        return cls(defs, data, storage, on_unlock)

    def unlocked(self, ident: str) -> bool:
        return ident in self.data.unlocked

    def counter(self, event: str) -> int:
        return self.data.counters.get(event, 0)

    def progress(self, ident: str) -> tuple[int, int]:
        """``(current, target)`` for an achievement, current capped at the target."""
        spec = self.defs[ident]
        current = len(self.data.rooms) if spec.rooms else self.counter(spec.event)
        return min(current, spec.target), spec.target

    def record(self, event: str, amount: int = 1) -> list[str]:
        """Count `amount` of `event`; returns the achievements this unlocked."""
        self.data.counters[event] = self.counter(event) + amount
        return self._check()

    def enter_room(self, room: str) -> list[str]:
        """Note a room entered; returns the achievements this unlocked."""
        if room in self.data.rooms:
            return []
        self.data.rooms.append(room)
        return self._check()

    def save(self) -> None:
        """Write progress (counters are saved with unlocks and when the game closes)."""
        if self.storage is not None:
            save_document(self.storage, ACHIEVEMENTS_KEY, ACHIEVEMENTS_CODEC, self.data)

    def _check(self) -> list[str]:
        earned = []
        for ident in self.defs:
            if not self.unlocked(ident) and self.progress(ident)[0] >= self.defs[ident].target:
                self.data.unlocked.append(ident)
                earned.append(ident)
                log.info("Achievement unlocked: %s", ident)
        if earned:
            self.save()
            for ident in earned:
                if self.on_unlock:
                    self.on_unlock(ident)
        return earned
