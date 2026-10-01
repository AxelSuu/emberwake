"""A play session's progress: stats, playtime, rooms seen, and writing it to the save slot."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from emberwake.game.data.save import save_slot
from emberwake.game.interact import Collected
from emberwake.game.player.controller import Dashed, Died, Jumped

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.core.events import EventBus
    from emberwake.engine.platform.storage import Storage
    from emberwake.engine.world.spawning import Spawner
    from emberwake.game.data.save import SaveSlot

log = logging.getLogger(__name__)


class Progress:
    """Keeps `data` current and saves it; saving is a no-op when `slot` is ``None``."""

    def __init__(self, data: SaveSlot, storage: Storage, slot: int | None) -> None:
        self.data = data
        self.storage = storage
        self.slot = slot

    def subscribe(self, bus: EventBus) -> list[Callable[[], None]]:
        stats = self.data.stats

        def collected(event: Collected) -> None:
            stats.embers += event.value

        def count(name: str) -> Callable[[object], None]:
            return lambda _: setattr(stats, name, getattr(stats, name) + 1)

        return [
            bus.subscribe(Jumped, count("jumps")),
            bus.subscribe(Dashed, count("dashes")),
            bus.subscribe(Died, count("deaths")),
            bus.subscribe(Collected, collected),
        ]

    def tick(self, dt: float) -> None:
        self.data.playtime += dt

    def discover(self, room_iid: str) -> None:
        if room_iid not in self.data.discovered:
            self.data.discovered.append(room_iid)

    def checkpoint(self, room: str, beacon: str, spawner: Spawner) -> None:
        """Continue at `beacon` from now on, and save."""
        self.data.room, self.data.beacon = room, beacon
        self.save(spawner)

    def save(self, spawner: Spawner) -> None:
        """Write progress (never the player's position) to the slot."""
        if self.slot is None:
            return
        spawner.snapshot_all()
        self.data.world = spawner.state
        save_slot(self.storage, self.slot, self.data)
        log.info("Saved slot %d at %s", self.slot, self.data.room)
