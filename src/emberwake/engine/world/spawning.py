"""Spawn LDtk entities as prefabs when their room loads, and save their state when it unloads.

Each spawned entity gets an `Identity` (its LDtk iid, room and prefab) and a `Body` covering its
LDtk rect in world pixels, plus its prefab's components. Components the prefab lists under
``persist`` are written to `WorldState` by iid when the room unloads (or on `snapshot_all`) and
restored when the entity spawns again. Entity refs stay iids; `Spawner.resolve` turns one into
the live entity, or ``None`` while its room is unloaded.

A gate (a predicate over LDtk entities, such as the game's flag conditions) holds entities back:
they spawn only while it lets them in, and `Spawner.regate` applies it again to a loaded room.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from emberwake.engine.core.serde import SerdeError, from_data, to_data
from emberwake.engine.ecs import COMPONENTS, component
from emberwake.engine.ecs.prefabs import build
from emberwake.engine.physics import Body

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from emberwake.engine.ecs import EntityId, Registry, World
    from emberwake.engine.ecs.prefabs import Prefab
    from emberwake.engine.world.ldtk import EntityInstance
    from emberwake.engine.world.rooms import Room

log = logging.getLogger(__name__)


@component
@dataclass(slots=True)
class Identity:
    """Where a spawned entity came from."""

    iid: str
    room: str
    prefab: str


@dataclass(slots=True)
class WorldState:
    """What changed in the world, by entity iid.

    Attributes:
        entities: Persisted component data, ``{iid: {component name: data}}``.
        removed: Entities taken out of play for good (a collected pickup); they never respawn.
    """

    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)


def prefab_name(identifier: str) -> str:
    """The prefab for an LDtk identifier: ``PressurePlate`` -> ``pressure_plate``."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", identifier).lower()


type Gate = Callable[[EntityInstance], bool]
"""Whether an LDtk entity belongs in the world now."""


class Spawner:
    """Spawns and despawns the entities of rooms as they load and unload.

    Args:
        world: Receives the entities.
        prefabs: By prefab name.
        state: Persisted components and retired iids; saved state is restored on spawn.
        registry: Component types by name.
        gate: Entities it rejects are held back until `regate` lets them in; all pass without.
    """

    def __init__(
        self,
        world: World,
        prefabs: Mapping[str, Prefab],
        state: WorldState,
        registry: Registry = COMPONENTS,
        gate: Gate | None = None,
    ) -> None:
        self.world = world
        self.prefabs = prefabs
        self.state = state
        self.registry = registry
        self.gate: Gate = gate or (lambda _: True)
        self.ids: dict[str, EntityId] = {}
        self.held: set[str] = set()
        """Iids of loaded rooms' entities the gate holds back."""
        self._warned: set[str] = set()

    def resolve(self, iid: str) -> EntityId | None:
        """The live entity with LDtk `iid`, or ``None`` if its room is not loaded or it died."""
        eid = self.ids.get(iid)
        return eid if eid is not None and self.world.reserved(eid) else None

    def spawn_room(self, room: Room) -> None:
        """Queue a spawn for every entity of `room` that has a prefab and is not live yet.

        Calling it on a loaded room brings back what was despawned without being retired, such
        as killed enemies (resting at a beacon does this). Entities the gate rejects are held back.
        """
        for entity in room.level.entities():
            if self.resolve(entity.iid) is not None or entity.iid in self.state.removed:
                continue
            if self.gate(entity):
                self.held.discard(entity.iid)
                self._spawn(room, entity)
            else:
                self.held.add(entity.iid)

    def regate(self, room: Room) -> None:
        """Apply the gate to loaded `room` again, after what it reads has changed.

        Live entities it now rejects are saved and despawned as if their room unloaded, and
        held-back ones it now lets in spawn. Entities killed or retired stay away.
        """
        for entity in room.level.entities():
            eid = self.resolve(entity.iid)
            if eid is not None and not self.gate(entity):
                self._save(eid, self.world.get(eid, Identity))
                self.world.despawn(eid)
                self.ids.pop(entity.iid, None)
                self.held.add(entity.iid)
            elif eid is None and entity.iid in self.held and self.gate(entity):
                self.held.discard(entity.iid)
                self._spawn(room, entity)

    def despawn_room(self, room: Room) -> None:
        """Save and queue a despawn for every entity spawned from `room`."""
        for eid, identity in list(self.world.query(Identity)):
            if identity.room == room.name and identity.iid not in self.state.removed:
                self._save(eid, identity)
                self.world.despawn(eid)
                self.ids.pop(identity.iid, None)
        self.held -= {entity.iid for entity in room.level.entities()}

    def retire(self, eid: EntityId) -> None:
        """Take a spawned entity out of play for good: despawn it and never spawn it again."""
        identity = self.world.get(eid, Identity)
        self.state.removed.append(identity.iid)
        self.ids.pop(identity.iid, None)
        self.world.despawn(eid)

    def snapshot_all(self) -> None:
        """Save the persisted components of every live entity, for writing a save file."""
        for eid, identity in self.world.query(Identity):
            self._save(eid, identity)

    def _spawn(self, room: Room, entity: EntityInstance) -> None:
        name = prefab_name(entity.identifier)
        prefab = self.prefabs.get(name)
        if prefab is None:
            if entity.identifier not in self._warned:
                self._warned.add(entity.identifier)
                log.warning("No prefab %r for LDtk entity %s", name, entity.identifier)
            return
        try:
            components = self._components(prefab, entity)
        except (KeyError, SerdeError) as error:
            log.error("Cannot spawn %s %s: %s", entity.identifier, entity.iid, error)
            return
        identity = Identity(entity.iid, room.name, name)
        self.ids[entity.iid] = self.world.spawn(identity, _body(room, entity), *components)

    def _components(self, prefab: Prefab, entity: EntityInstance) -> list[object]:
        components = build(prefab, entity.values(), self.registry)
        for name, data in self.state.entities.get(entity.iid, {}).items():
            if name in prefab.persist and name in components:
                components[name] = from_data(self.registry[name], data)
        return list(components.values())

    def _save(self, eid: EntityId, identity: Identity) -> None:
        prefab = self.prefabs.get(identity.prefab)
        if prefab is None or not prefab.persist:
            return
        saved = self.state.entities.setdefault(identity.iid, {})
        for name in prefab.persist:
            value = self.world.find(eid, self.registry[name])
            if value is not None:
                saved[name] = to_data(value)


def _body(room: Room, entity: EntityInstance) -> Body:
    x = room.rect.x + entity.px[0] - entity.pivot[0] * entity.width
    y = room.rect.y + entity.px[1] - entity.pivot[1] * entity.height
    return Body(x, y, entity.width, entity.height)
