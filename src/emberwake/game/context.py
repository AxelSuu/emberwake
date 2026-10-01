"""Shared services handed to every game scene."""

from __future__ import annotations

from dataclasses import dataclass

from emberwake.engine.core.events import EventBus
from emberwake.engine.platform.storage import Storage
from emberwake.game.data.settings import Settings


@dataclass(slots=True)
class GameContext:
    storage: Storage
    settings: Settings
    bus: EventBus
    canvas_size: tuple[int, int]
    dev: bool = False
    slot: int = 1
    """Save slot the game continues from and saves to."""
    new_game: bool = False
    """Ignore the slot's progress and start over (it is overwritten at the first save)."""
