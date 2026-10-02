from __future__ import annotations

import functools
import logging
import tomllib
from typing import TYPE_CHECKING

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.dialogue import holds
from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.physics import Body
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import RoomGraph, RoomStreamer, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game import paths
from emberwake.game.data.save import SaveSlot
from emberwake.game.enemies import Brain
from emberwake.game.flags import Facts, admits, flag_system, flags_in, gate_system
from emberwake.game.interact import Pickup, Switch, trigger_system
from emberwake.game.player.controller import Motor
from emberwake.game.scenes.gameplay import COLLISIONS
from emberwake.game.signals import Door, Wiring, door_system, signal_system

if TYPE_CHECKING:
    import pytest

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
DOOR = "#...........d......#"
HALL = "\n".join([WALL, *[INSIDE] * 6, DOOR, DOOR, "#.P.a..e..u.d.z....#", WALL])
FAR = "\n".join([WALL, *[INSIDE] * 8, "#.s................#", WALL])
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
[entities.d]
type = "Door"
[entities.z]
type = "SetFlag"
fields = { Flag = "steps", Mode = "add", Value = 2 }
"""
FAR_TOML = """
[entities.s]
type = "FlagSwitch"
fields = { Condition = "open", Targets = ["Hall:d"] }
"""
FEET = 10 * 16


class Rig:
    """Hall streamed in with the game's gate and the systems flags touch.

    Far, which never loads, holds a FlagSwitch wired to Hall's door.
    """

    def __init__(self, toml: str = TOML) -> None:
        hall = make_room("Hall", (0, 0), HALL, from_data(RoomFile, tomllib.loads(toml)))
        far = make_room("Far", (0, 3), FAR, from_data(RoomFile, tomllib.loads(FAR_TOML)))
        project = from_data(Project, build_project(Source(DEFS, [hall, far])))
        self.data = SaveSlot(room="Hall")
        self.facts = Facts(self.data.flags, self.data.abilities, self.data.inventory)
        self.world = World()
        gate = functools.partial(admits, facts=self.facts)
        self.spawner = Spawner(self.world, PREFABS, self.data.world, gate=gate)
        self.grid = WorldGrid()
        self.rooms = RoomStreamer(
            RoomGraph(project.levels),
            self.grid,
            "Collisions",
            COLLISIONS,
            on_load=self.spawner.spawn_room,
            on_unload=self.spawner.despawn_room,
        )
        wiring = Wiring.from_levels(project.levels, PREFABS)
        for resource in (self.facts, self.spawner, self.rooms, self.grid, wiring, EventBus()):
            self.world.insert_resource(resource)
        self.rooms.enter("Hall")
        self.body = Body(0, FEET - 20, 10, 20)
        self.world.spawn(self.body, Motor())
        self.schedule = Schedule(["post"])
        for system in (trigger_system, flag_system, gate_system, signal_system, door_system):
            self.schedule.add("post", system)
        self.step()

    def at(self, column: float) -> Rig:
        self.body.x = column * 16 + 3
        return self

    def step(self, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.schedule.run(self.world, 1 / 60)
        return self

    def prefabs(self) -> list[str]:
        return sorted(identity.prefab for _, identity in self.world.query(Identity))

    def embers(self) -> list[int]:
        return sorted(pickup.value for _, pickup in self.world.query(Pickup))

    def door_open(self) -> bool:
        ((_, door),) = self.world.query(Door)
        return door.open


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
    assert rig.prefabs() == ["door", "ember", "player_start", "set_flag"]
    assert rig.embers() == [7]


def test_entities_come_and_go_live_as_facts_change():
    rig = Rig()
    rig.data.flags["open"] = 1
    rig.data.inventory["shard"] = 2
    rig.step()
    assert rig.prefabs() == ["door", "ember", "lever", "player_start", "set_flag"]
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


def test_a_flag_switch_powers_its_door_from_a_room_that_is_not_loaded():
    rig = Rig()
    assert "Far" not in rig.rooms.loaded
    assert not rig.door_open()
    rig.data.flags["open"] = 1
    rig.step()
    assert rig.door_open()
    del rig.data.flags["open"]
    rig.step()
    assert not rig.door_open()


def test_touching_a_set_flag_sets_or_adds():
    rig = Rig()
    rig.at(14).step()
    assert rig.data.flags["steps"] == 2
    rig.step(3)
    assert rig.data.flags["steps"] == 2
    rig.at(0).step().at(14).step()
    assert rig.data.flags["steps"] == 4


def test_a_set_flag_with_mode_set_overwrites():
    rig = Rig(TOML.replace('"add"', '"set"'))
    rig.data.flags["steps"] = 9
    rig.at(14).step()
    assert rig.data.flags["steps"] == 2


def test_a_set_flag_with_unless_on_its_own_flag_fires_once():
    rig = Rig(TOML.replace("Value = 2", 'Value = 2, Unless = "steps"'))
    rig.at(14).step(2)
    assert rig.data.flags["steps"] == 2
    assert "set_flag" not in rig.prefabs()
    rig.at(0).step().at(14).step()
    assert rig.data.flags["steps"] == 2


def test_flags_in_lists_what_the_levels_read_and_write():
    rig = Rig()
    assert flags_in(rig.rooms.graph.levels.values()) == {"open", "steps"}


def test_a_killed_enemy_and_a_collected_pickup_stay_gone_when_flags_change():
    toml = """
[entities.a]
type = "Lever"
[entities.e]
type = "Ember"
fields = { Requires = "open" }
[entities.u]
type = "Clockrat"
fields = { Requires = "open" }
[entities.d]
type = "Door"
[entities.z]
type = "SetFlag"
"""
    rig = Rig(toml)
    rig.data.flags["open"] = 1
    rig.step()
    ((rat, _),) = rig.world.query(Brain)
    ((ember, _),) = rig.world.query(Pickup)
    rig.world.despawn(rat)
    rig.spawner.retire(ember)
    for flags in ({}, {"open": 1}, {}, {"open": 1}):
        rig.data.flags.clear()
        rig.data.flags.update(flags)
        rig.step()
        assert rig.prefabs() == ["door", "lever", "player_start", "set_flag"]


def test_a_malformed_condition_holds_the_entity_back(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.ERROR):
        rig = Rig(TOML.replace('Unless = "open"', 'Unless = "open >"'))
    assert rig.embers() == []
    assert "held back" in caplog.text
