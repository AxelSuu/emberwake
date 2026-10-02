"""World flags: conditions that decide which entities are in the world, and what sets them.

Any LDtk entity can carry ``Requires`` and ``Unless`` in the dialogue's condition syntax. They read
`Facts`: the save's flags, plus ``has.<thing>`` for abilities and item counts.
See ``docs/specs/world-flags.md``.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from emberwake.engine.core.dialogue import DialogueError, flag_of, holds
from emberwake.engine.ecs import component
from emberwake.engine.world.rooms import RoomStreamer
from emberwake.engine.world.spawning import Spawner
from emberwake.game.interact import Trigger

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from emberwake.engine.ecs import World
    from emberwake.engine.world.ldtk import EntityInstance, Level

log = logging.getLogger(__name__)

HAS = "has."
REQUIRES, UNLESS = "Requires", "Unless"


@component
@dataclass(slots=True)
class FlagSwitch:
    """A signal source that is on while its condition holds; `Wiring` evaluates it."""

    condition: str = ""
    targets: list[str] = field(default_factory=list)


@component
@dataclass(slots=True)
class SetFlag:
    """Set or increment a save flag the first time the player enters its trigger."""

    flag: str = ""
    value: int = 1
    mode: Literal["set", "add"] = "set"
    fired: bool = False


class Facts(Mapping[str, int]):
    """What conditions read: flags, and ``has.<thing>`` for abilities (1) and item counts.

    A view of the save's own flags, abilities and inventory, so it never goes stale.
    """

    def __init__(
        self, flags: dict[str, int], abilities: list[str], inventory: dict[str, int]
    ) -> None:
        self.flags = flags
        self.abilities = abilities
        self.inventory = inventory
        self._seen = self._snapshot()

    def __getitem__(self, name: str) -> int:
        if not name.startswith(HAS):
            return self.flags[name]
        thing = name.removeprefix(HAS)
        if value := 1 if thing in self.abilities else self.inventory.get(thing, 0):
            return value
        raise KeyError(name)

    def __iter__(self) -> Iterator[str]:
        yield from self.flags
        yield from (HAS + ability for ability in self.abilities)
        yield from (HAS + item for item, count in self.inventory.items() if count)

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def changed(self) -> bool:
        """Whether anything changed since the last call, or since the view was made."""
        seen = self._snapshot()
        if seen == self._seen:
            return False
        self._seen = seen
        return True

    def _snapshot(self) -> tuple[object, ...]:
        return tuple(self.flags.items()), tuple(self.abilities), tuple(self.inventory.items())


def admits(entity: EntityInstance, facts: Mapping[str, int]) -> bool:
    """Whether `entity` belongs in the world: its Requires holds and its Unless does not.

    A malformed condition holds the entity back. A PlayerStart always belongs.
    """
    if entity.identifier == "PlayerStart":
        return True
    requires, unless = entity.field(REQUIRES), entity.field(UNLESS)
    try:
        return (not requires or holds(requires, facts)) and not (unless and holds(unless, facts))
    except DialogueError as error:
        log.error("%s %s held back: %s", entity.identifier, entity.iid, error)
        return False


def flags_in(levels: Iterable[Level]) -> set[str]:
    """The save flags the levels read (Requires, Unless, Condition) or write (SetFlag, Beacon)."""
    names: set[str] = set()
    for level in levels:
        for entity in level.entities():
            for field_name in (REQUIRES, UNLESS, "Condition"):
                if condition := entity.field(field_name):
                    with contextlib.suppress(DialogueError):
                        names.add(flag_of(condition))
            if entity.identifier in ("SetFlag", "Beacon") and (flag := entity.field("Flag")):
                names.add(flag)
    return {name for name in names if not name.startswith(HAS)}


def holds_safely(condition: str, facts: Mapping[str, int]) -> bool:
    """Whether `condition` holds; a malformed one never does."""
    try:
        return holds(condition, facts)
    except DialogueError:
        return False


def gate_system(world: World, dt: float) -> None:
    """When the facts change, gated entities of loaded rooms come and go."""
    if world.resource(Facts).changed():
        spawner = world.resource(Spawner)
        for room in world.resource(RoomStreamer).loaded.values():
            spawner.regate(room)


def flag_system(world: World, dt: float) -> None:
    """Apply SetFlag zones the player has stepped into."""
    flags = world.resource(Facts).flags
    for _, trigger, zone in world.query(Trigger, SetFlag):
        if trigger.inside and not zone.fired and zone.flag:
            base = flags.get(zone.flag, 0) if zone.mode == "add" else 0
            flags[zone.flag] = base + zone.value
        zone.fired = trigger.inside
