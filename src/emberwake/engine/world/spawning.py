"""Spawn LDtk entities as prefabs when their room loads, and save their state when it unloads.

Each spawned entity gets an `Identity` (its LDtk iid, room and prefab) and a `Body` covering its
LDtk rect in world pixels, plus its prefab's components. Components the prefab lists under
``persist`` are written to `WorldState` by iid when the room unloads (or on `snapshot_all`) and
restored when the entity spawns again. Entity refs stay iids; `Spawner.resolve` turns one into
the live entity, or ``None`` while its room is unloaded.
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
    from collections.abc import Mapping

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
    """Persisted component data by entity iid: ``{iid: {component name: data}}``."""

    entities: dict[str, dict[str, Any]] = field(default_factory=dict)


def prefab_name(identifier: str) -> str:
    """The prefab for an LDtk identifier: ``PressurePlate`` -> ``pressure_plate``."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", identifier).lower()


class Spawner:
    """Spawns and despawns the entities of rooms as they load and unload."""

    def __init__(
        self,
        world: World,
        prefabs: Mapping[str, Prefab],
        state: WorldState,
        registry: Registry = COMPONENTS,
    ) -> None:
        self.world = world
        self.prefabs = prefabs
        self.state = state
        self.registry = registry
        self.ids: dict[str, EntityId] = {}
        self._warned: set[str] = set()

    def resolve(self, iid: str) -> EntityId | None:
        """The live entity with LDtk `iid`, or ``None`` if its room is not loaded."""
        return self.ids.get(iid)

    def spawn_room(self, room: Room) -> None:
        """Queue a spawn for every entity of `room` that has a prefab and is not live yet."""
        for entity in room.level.entities():
            if entity.iid in self.ids:
                continue
            name = prefab_name(entity.identifier)
            prefab = self.prefabs.get(name)
            if prefab is None:
                if entity.identifier not in self._warned:
                    self._warned.add(entity.identifier)
                    log.warning("No prefab %r for LDtk entity %s", name, entity.identifier)
                continue
            try:
                components = self._components(prefab, entity)
            except (KeyError, SerdeError) as error:
                log.error("Cannot spawn %s %s: %s", entity.identifier, entity.iid, error)
                continue
            identity = Identity(entity.iid, room.name, name)
            body = _body(room, entity)
            self.ids[entity.iid] = self.world.spawn(identity, body, *components)

    def despawn_room(self, room: Room) -> None:
        """Save and queue a despawn for every entity spawned from `room`."""
        for eid, identity in list(self.world.query(Identity)):
            if identity.room == room.name:
                self._save(eid, identity)
                self.world.despawn(eid)
                del self.ids[identity.iid]

    def snapshot_all(self) -> None:
        """Save the persisted components of every live entity, for writing a save file."""
        for eid, identity in self.world.query(Identity):
            self._save(eid, identity)

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
