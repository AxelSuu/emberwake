"""Signals from switches to receivers, and doors that open while powered."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from emberwake.engine.ecs import component
from emberwake.engine.physics import Body, Tile
from emberwake.engine.world.rooms import WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner, prefab_name
from emberwake.game.flags import Facts, holds_safely
from emberwake.game.interact import Switch, overlap, player_body

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from emberwake.engine.ecs import World
    from emberwake.engine.ecs.prefabs import Prefab
    from emberwake.engine.world.ldtk import Level

TARGETS = ("Switch.targets", "FlagSwitch.targets")
LOCKS = ("Encounter.doors",)
"""Fields naming doors an encounter shuts; they power nothing."""
CONDITION = "FlagSwitch.condition"


@component
@dataclass(slots=True)
class Receiver:
    mode: Literal["any", "all"] = "any"
    invert: bool = False
    powered: bool = False


@component
@dataclass(slots=True)
class Door:
    open: bool = False


@dataclass(slots=True)
class Wiring:
    """Every receiver's sources across the whole world, so unloaded switches still count."""

    sources: dict[str, list[str]] = field(default_factory=dict)
    conditions: dict[str, str] = field(default_factory=dict)
    """FlagSwitch iid -> its condition; they are read from the level, never from saved state."""
    locks: dict[str, list[str]] = field(default_factory=dict)
    """Door iid -> the encounters that shut it."""

    @classmethod
    def from_levels(cls, levels: Iterable[Level], prefabs: Mapping[str, Prefab]) -> Wiring:
        sources: defaultdict[str, list[str]] = defaultdict(list)
        conditions: dict[str, str] = {}
        locks: defaultdict[str, list[str]] = defaultdict(list)
        for level in levels:
            for entity in level.entities():
                prefab = prefabs.get(prefab_name(entity.identifier))
                if prefab is None:
                    continue
                values = entity.values()
                for name, target in prefab.fields.items():
                    if target in TARGETS:
                        for receiver in values.get(name) or []:
                            sources[receiver].append(entity.iid)
                    elif target in LOCKS:
                        for door in values.get(name) or []:
                            locks[door].append(entity.iid)
                    elif target == CONDITION:
                        conditions[entity.iid] = values.get(name) or ""
        wired = {target: sorted(iids) for target, iids in sources.items()}
        return cls(wired, conditions, {door: sorted(iids) for door, iids in locks.items()})


def signal_system(world: World, dt: float) -> None:
    """Power receivers from their sources, one pass in iid order.

    Doors an encounter shuts are left to `lock_system`.
    """
    wiring, spawner, facts = world.resource(Wiring), world.resource(Spawner), world.resource(Facts)

    def on(iid: str) -> bool:
        if iid in wiring.conditions:
            return holds_safely(wiring.conditions[iid], facts)
        eid = spawner.resolve(iid)
        if eid is not None:
            switch = world.find(eid, Switch)
            return switch is not None and switch.on
        saved = spawner.state.entities.get(iid, {}).get("Switch", {})
        return bool(saved.get("on", False))

    receivers = sorted(world.query(Identity, Receiver), key=lambda row: row[1].iid)
    for _, identity, receiver in receivers:
        if identity.iid in wiring.locks:
            continue
        states = [on(iid) for iid in wiring.sources.get(identity.iid, [])]
        powered = any(states) if receiver.mode == "any" else bool(states) and all(states)
        receiver.powered = powered != receiver.invert


def door_system(world: World, dt: float) -> None:
    """Doors open while powered; closing waits until the player is out of the doorway."""
    grid, player = world.resource(WorldGrid), player_body(world)
    for _, body, door, receiver in world.query(Body, Door, Receiver):
        blocked = player is not None and overlap(body, player)
        door.open = receiver.powered or (door.open and blocked)
        tile = Tile.EMPTY if door.open else Tile.SOLID
        size = grid.tile_size
        for row in range(math.floor(body.y / size), math.ceil((body.y + body.height) / size)):
            for column in range(math.floor(body.x / size), math.ceil((body.x + body.width) / size)):
                grid.set(column, row, tile)
