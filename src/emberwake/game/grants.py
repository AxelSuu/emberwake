"""Abilities and items: what the player has found, how it is given, and what it adds up to.

Both live in the save slot; `Loadout` is the world's view of them. Things are named in
``content/grants.toml``; a `Grant` pickup or the dialogue action ``give:<thing>`` hands them out.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Spawner
from emberwake.game.interact import overlap, player_body

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.engine.ecs import World

START = ("dash",)
"""Abilities a new game begins with; the swing needs none."""
SHARDS_PER_HEALTH = 3
FLAME_PER_FLASK = 20.0


@dataclass(slots=True)
class GrantSpec:
    kind: Literal["ability", "item"] = "item"
    max: int = 1
    """The most of an item the player can carry."""


def load_grants(path: Path) -> dict[str, GrantSpec]:
    """Parse ``grants.toml``. Raises `tomllib.TOMLDecodeError` or `SerdeError`."""
    return from_data(dict[str, GrantSpec], tomllib.loads(path.read_text(encoding="utf-8")))


@dataclass(slots=True)
class Loadout:
    """What the player has: the save slot's own lists, so changes are saved with it."""

    abilities: list[str] = field(default_factory=lambda: list(START))
    inventory: dict[str, int] = field(default_factory=dict)
    specs: dict[str, GrantSpec] = field(default_factory=dict)

    def has(self, ability: str) -> bool:
        return ability in self.abilities

    def count(self, item: str) -> int:
        return self.inventory.get(item, 0)

    def give(self, thing: str, count: int = 1) -> bool:
        """Add `thing`; returns whether anything changed (unknown things and full stacks do not)."""
        spec = self.specs.get(thing)
        if spec is None:
            return False
        if spec.kind == "ability":
            if thing in self.abilities:
                return False
            self.abilities.append(thing)
            return True
        held = self.count(thing)
        new = min(held + count, spec.max)
        self.inventory[thing] = new
        return new != held

    @property
    def bonus_health(self) -> int:
        return self.count("shard") // SHARDS_PER_HEALTH

    @property
    def bonus_flame(self) -> float:
        return self.count("oil_flask") * FLAME_PER_FLASK

    @property
    def bonus_flares(self) -> int:
        return self.count("flare_pouch")


@component
@dataclass(slots=True)
class Grant:
    """A pickup that gives `thing` (an ability or `count` of an item) when touched."""

    thing: str = ""
    count: int = 1


GIVE = "give:"
"""Dialogue actions ``give:<thing>`` hand `thing` to the player."""


@dataclass(frozen=True, slots=True)
class Give:
    """Something (a dialogue) asks for `thing` to be given to the player."""

    thing: str
    count: int = 1


@dataclass(frozen=True, slots=True)
class Granted:
    thing: str
    count: int = 1


def grant_system(world: World, dt: float) -> None:
    """Touching a grant gives what it holds and takes it out of play for good."""
    player = player_body(world)
    if player is None:
        return
    loadout, bus = world.resource(Loadout), world.resource(EventBus)
    for eid, body, grant in list(world.query(Body, Grant)):
        if overlap(body, player):
            if loadout.give(grant.thing, grant.count):
                bus.publish(Granted(grant.thing, grant.count))
            world.resource(Spawner).retire(eid)
