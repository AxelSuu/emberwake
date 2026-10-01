"""Shared services handed to every game scene."""

from __future__ import annotations

from dataclasses import dataclass, field

from emberwake.engine.audio import Audio
from emberwake.engine.core.events import EventBus
from emberwake.engine.core.i18n import Strings
from emberwake.engine.platform.storage import Storage
from emberwake.game.achievements import Achievements
from emberwake.game.data.settings import Settings


@dataclass(slots=True)
class GameContext:
    storage: Storage
    settings: Settings
    bus: EventBus
    canvas_size: tuple[int, int]
    dev: bool = False
    strings: Strings = field(default_factory=Strings)
    """String tables for the player's language (`t`)."""
    achievements: Achievements = field(default_factory=Achievements)
    """Lifetime counters and unlocks; empty unless the app loads definitions."""
    audio: Audio = field(default_factory=Audio)
    """Sound and music; silent unless the app gives it a sound directory."""
    slot: int = 1
    """Save slot the game continues from and saves to."""
    new_game: bool = False
    """Ignore the slot's progress and start over (it is overwritten at the first save)."""

    def t(self, key: str, **values: object) -> str:
        """The text for `key` in the player's language."""
        return self.strings.t(key, **values)
