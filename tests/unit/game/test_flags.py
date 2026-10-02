from __future__ import annotations

import functools
import logging
import tomllib
from typing import TYPE_CHECKING

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.dialogue import holds
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import RoomGraph, RoomStreamer, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game import paths
from emberwake.game.data.save import SaveSlot
from emberwake.game.flags import Facts, admits, gate_system
from emberwake.game.interact import Pickup, Switch
from emberwake.game.scenes.gameplay import COLLISIONS

if TYPE_CHECKING:
    import pytest

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
HALL = "\n".join([WALL, *[INSIDE] * 8, "#.P.a..e..u........#", WALL])
TOML = """
[entities.a]
type = "Lever"
fields = { Requires = "open" }
[entities.e]
type = "Ember"
fields = { Requires = "has.shard>=2" }
[entities.u]
type = "Ember"
fields = { Unless = "open", Value = 7 }
"""


class Rig:
    """One room streamed in with the game's gate, its spawner and the gate system."""

    def __init__(self, toml: str = TOML) -> None:
        hall = make_room("Hall", (0, 0), HALL, from_data(RoomFile, tomllib.loads(toml)))
        project = from_data(Project, build_project(Source(DEFS, [hall])))
        self.data = SaveSlot(room="Hall")
        self.facts = Facts(self.data.flags, self.data.abilities, self.data.inventory)
        self.world = World()
        gate = functools.partial(admits, facts=self.facts)
        self.spawner = Spawner(self.world, PREFABS, self.data.world, gate=gate)
        self.rooms = RoomStreamer(
            RoomGraph(project.levels),
            WorldGrid(),
            "Collisions",
            COLLISIONS,
            on_load=self.spawner.spawn_room,
            on_unload=self.spawner.despawn_room,
        )
        for resource in (self.facts, self.spawner, self.rooms):
            self.world.insert_resource(resource)
        self.rooms.enter("Hall")
        self.schedule = Schedule(["post"])
        self.schedule.add("post", gate_system)
        self.step()

    def step(self, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.schedule.run(self.world, 1 / 60)
        return self

    def prefabs(self) -> list[str]:
        return sorted(identity.prefab for _, identity in self.world.query(Identity))

    def embers(self) -> list[int]:
        return sorted(pickup.value for _, pickup in self.world.query(Pickup))


def test_has_reads_abilities_and_item_counts():
    facts = Facts({"met": 2}, ["dash"], {"shard": 3, "key": 0})
    assert facts["has.dash"] == 1
    assert facts["has.shard"] == 3
    assert facts.get("has.key", 0) == facts.get("has.flare", 0) == 0
    assert dict(facts) == {"met": 2, "has.dash": 1, "has.shard": 3}
    assert holds("has.shard>=3", facts)
    assert holds("met==2", facts)
    assert not holds("has.flare", facts)


def test_changed_notices_flags_abilities_and_items():
    data = SaveSlot(room="Hall")
    facts = Facts(data.flags, data.abilities, data.inventory)
    assert not facts.changed()
    for change in (
        lambda: data.flags.update(met=1),
        lambda: data.abilities.append("flare"),
        lambda: data.inventory.update(shard=1),
    ):
        change()
        assert facts.changed()
        assert not facts.changed()


def test_requires_and_unless_decide_what_spawns_with_the_room():
    rig = Rig()
    assert rig.prefabs() == ["ember", "player_start"]
    assert rig.embers() == [7]


def test_entities_come_and_go_live_as_facts_change():
    rig = Rig()
    rig.data.flags["open"] = 1
    rig.data.inventory["shard"] = 2
    rig.step()
    assert rig.prefabs() == ["ember", "lever", "player_start"]
    assert rig.embers() == [1]
    rig.data.flags["open"] = 0
    rig.step()
    assert rig.embers() == [1, 7]


def test_a_held_back_switch_keeps_its_state():
    rig = Rig()
    rig.data.flags["open"] = 1
    rig.step()
    ((eid, switch, _),) = rig.world.query(Switch, Identity)
    switch.on = True
    del rig.data.flags["open"]
    rig.step()
    assert rig.world.count(Switch) == 0
    rig.data.flags["open"] = 1
    rig.step()
    ((_, switch),) = rig.world.query(Switch)
    assert switch.on
    assert eid not in rig.world


def test_a_malformed_condition_holds_the_entity_back(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.ERROR):
        rig = Rig(TOML.replace('Unless = "open"', 'Unless = "open >"'))
    assert rig.embers() == []
    assert "held back" in caplog.text
