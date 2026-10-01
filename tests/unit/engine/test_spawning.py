from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import Registry, World
from emberwake.engine.ecs.prefabs import Prefab
from emberwake.engine.physics import Body, Tile
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import Room, RoomGraph
from emberwake.engine.world.spawning import Identity, Spawner, WorldState, prefab_name
from emberwake.game import paths

if TYPE_CHECKING:
    import pytest

REGISTRY = Registry()
REGISTRY.register(Identity)


@REGISTRY.register
@dataclass(slots=True)
class Wired:
    targets: list[str] = field(default_factory=list)
    on: bool = False


@REGISTRY.register
@dataclass(slots=True)
class Value:
    amount: int = 1


PREFABS = {
    "lever": Prefab(
        components={"Wired": {}}, fields={"Targets": "Wired.targets"}, persist=["Wired"]
    ),
    "door": Prefab(),
    "ember": Prefab(components={"Value": {}}, fields={"Value": "Value.amount"}),
}
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
DOOR = "#..b" + "." * 15 + "#"
HALL = "\n".join([WALL, *[INSIDE] * 6, DOOR, DOOR, "#.Pb.a..e.e" + "." * 8 + "#", WALL])
HALL_TOML = """
[entities.a]
type = "Lever"
fields = { Targets = ["b"] }
[entities.b]
type = "Door"
[entities.e]
type = "Ember"
"""


def room() -> Room:
    defs = read_toml(Defs, paths.levels("src/defs.toml"))
    hall = make_room("Hall", (1, 0), HALL, from_data(RoomFile, tomllib.loads(HALL_TOML)))
    level = RoomGraph(from_data(Project, build_project(Source(defs, [hall]))).levels).levels["Hall"]
    return Room(level, level.layer("Collisions").to_tile_grid({1: Tile.SOLID}))


def spawner(state: WorldState | None = None) -> Spawner:
    return Spawner(World(), PREFABS, state or WorldState(), REGISTRY)


class Spawned(NamedTuple):
    identity: Identity
    body: Body
    wired: Wired | None
    value: Value | None


def entities(s: Spawner, prefab: str) -> list[Spawned]:
    world = s.world
    return [
        Spawned(identity, world.get(eid, Body), world.find(eid, Wired), world.find(eid, Value))
        for eid, identity in world.query(Identity)
        if identity.prefab == prefab
    ]


def test_prefab_names_are_snake_case():
    assert [prefab_name(n) for n in ("Lever", "PressurePlate", "PlayerStart")] == [
        "lever",
        "pressure_plate",
        "player_start",
    ]


def test_spawns_prefabs_with_bodies_identity_and_mapped_refs(caplog: pytest.LogCaptureFixture):
    s, r = spawner(), room()
    with caplog.at_level(logging.WARNING):
        s.spawn_room(r)
        s.spawn_room(r)
    assert caplog.text.count("No prefab 'player_start'") == 1
    s.world.flush()
    ((door, door_body, *_),) = entities(s, "door")
    ((lever, lever_body, wired, _),) = entities(s, "lever")
    assert door_body == Body(320 + 3 * 16, 7 * 16, 16, 48)
    assert lever_body == Body(320 + 5 * 16, 9 * 16, 16, 16)
    assert (lever.room, wired) == ("Hall", Wired([door.iid]))
    assert s.resolve(door.iid) is not None
    assert [value for *_, value in entities(s, "ember")] == [Value(1), Value(1)]


def test_unloading_saves_persisted_components_and_restores_them():
    state = WorldState()
    s, r = spawner(state), room()
    s.spawn_room(r)
    s.world.flush()
    ((lever, _, wired, _),) = entities(s, "lever")
    assert wired is not None
    wired.on = True
    s.despawn_room(r)
    s.world.flush()
    assert entities(s, "lever") == []
    assert s.resolve(lever.iid) is None
    assert state.entities == {lever.iid: {"Wired": {"targets": wired.targets, "on": True}}}

    again = spawner(state)
    again.spawn_room(r)
    again.world.flush()
    ((_, _, restored, _),) = entities(again, "lever")
    assert restored is not None
    assert restored.on


def test_snapshot_all_saves_without_despawning():
    state = WorldState()
    s = spawner(state)
    s.spawn_room(room())
    s.world.flush()
    s.snapshot_all()
    assert len(state.entities) == 1
    assert len(entities(s, "lever")) == 1


def test_bad_field_values_skip_the_entity(caplog: pytest.LogCaptureFixture):
    broken = {**PREFABS, "ember": Prefab(components={"Value": {"amount": "x"}})}
    s = Spawner(World(), broken, WorldState(), REGISTRY)
    with caplog.at_level(logging.ERROR):
        s.spawn_room(room())
    s.world.flush()
    assert entities(s, "ember") == []
    assert "Cannot spawn Ember" in caplog.text


def test_retired_entities_never_respawn():
    state = WorldState()
    s, r = spawner(state), room()
    s.spawn_room(r)
    s.world.flush()
    (ember, _), *_ = [(eid, i) for eid, i in s.world.query(Identity) if i.prefab == "ember"]
    iid = s.world.get(ember, Identity).iid
    s.retire(ember)
    s.despawn_room(r)
    s.world.flush()
    assert state.removed == [iid]
    s.spawn_room(r)
    s.world.flush()
    assert len(entities(s, "ember")) == 1
    assert s.resolve(iid) is None
