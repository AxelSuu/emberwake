from __future__ import annotations

import tomllib
from typing import Any

import pytest
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, Tile, TileSource
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import Room, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner, WorldState
from emberwake.game import paths
from emberwake.game.actions import Action
from emberwake.game.beacons import Beacon, BeaconLit, beacon_system
from emberwake.game.interact import (
    Collected,
    Interactable,
    Interacted,
    Switch,
    SwitchChanged,
    interact_system,
    pickup_system,
    plate_system,
    trigger_system,
)
from emberwake.game.player.controller import Motor
from emberwake.game.player.tuning import PlayerTuning
from emberwake.game.render.sprites import sprite_system
from emberwake.game.scenes.gameplay import COLLISIONS
from emberwake.game.signals import Door, Receiver, Wiring, door_system, signal_system

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
DOOR = "#......b...........#"
HALL = "\n".join([WALL, *[INSIDE] * 6, DOOR, DOOR, "#.P.a..b..p..e..k..#", WALL])
TOML = """
[entities.a]
type = "Lever"
fields = { Targets = ["b"] }
[entities.b]
type = "Door"
[entities.p]
type = "PressurePlate"
fields = { Targets = ["b"] }
[entities.e]
type = "Ember"
fields = { Value = 5 }
[entities.k]
type = "Beacon"
"""
FEET = 10 * 16


class Rig:
    def __init__(self, toml: str = TOML, state: WorldState | None = None) -> None:
        room_file = from_data(RoomFile, tomllib.loads(toml))
        hall = make_room("Hall", (0, 0), HALL, room_file)
        project = from_data(Project, build_project(Source(DEFS, [hall])))
        level = project.levels[0]
        self.world = World()
        self.grid = WorldGrid()
        self.grid.add(Room(level, level.layer("Collisions").to_tile_grid(COLLISIONS)))
        self.spawner = Spawner(self.world, PREFABS, state or WorldState())
        self.actions = InputState[Action]()
        self.bus = EventBus()
        self.events: list[object] = []
        for kind in (Interacted, SwitchChanged, Collected, BeaconLit):
            self.bus.subscribe(kind, self.events.append)
        for resource in (self.actions, self.bus, self.spawner, self.grid):
            self.world.insert_resource(resource)
        self.world.insert_resource(self.grid, key=TileSource)
        self.world.insert_resource(PlayerTuning())
        self.world.insert_resource(Wiring.from_levels(project.levels, PREFABS))
        self.spawner.spawn_room(self.grid.rooms[0])
        self.body = Body(0, FEET - 20, 10, 20)
        self.motor = Motor()
        self.world.spawn(self.body, self.motor)
        self.schedule = Schedule(["logic", "post", "render_prep"])
        self.schedule.add("logic", interact_system)
        self.schedule.add("logic", beacon_system)
        for system in (trigger_system, plate_system, pickup_system, signal_system, door_system):
            self.schedule.add("post", system)
        self.schedule.add("render_prep", sprite_system)
        self.tick()

    def at(self, column: float) -> Rig:
        self.body.x = column * 16 + 3
        return self

    def tick(self, *actions: Action) -> Rig:
        self.actions.advance(frozenset(actions))
        self.schedule.run(self.world, 1 / 60)
        return self

    def one(self, prefab: str, tp: type[Any]) -> Any:
        (found,) = [
            self.world.get(eid, tp)
            for eid, identity in self.world.query(Identity)
            if identity.prefab == prefab
        ]
        return found

    @property
    def door_tile(self) -> Tile:
        return self.grid.get(7, 8)


def test_doors_start_closed_and_solid():
    rig = Rig()
    assert not rig.one("door", Door).open
    assert rig.door_tile is Tile.SOLID


def test_lever_toggles_the_door():
    rig = Rig().at(4).tick()
    assert rig.one("lever", Interactable).in_range
    rig.tick(Action.INTERACT)
    assert rig.one("lever", Switch).on
    assert rig.one("door", Receiver).powered
    assert rig.one("door", Door).open
    assert rig.door_tile is Tile.EMPTY
    lever_iid = rig.one("lever", Identity).iid
    assert rig.events == [Interacted(lever_iid), SwitchChanged(lever_iid, True)]
    rig.tick(Action.INTERACT)
    assert rig.one("lever", Switch).on, "held, not pressed again"
    rig.tick().tick(Action.INTERACT)
    assert rig.events[-1] == SwitchChanged(lever_iid, False)
    assert not rig.one("door", Door).open
    assert rig.door_tile is Tile.SOLID


def test_out_of_reach_does_nothing():
    rig = Rig().at(1).tick(Action.INTERACT)
    assert not rig.one("lever", Interactable).in_range
    assert not rig.one("lever", Switch).on


def lever_mode(mode: str) -> str:
    return TOML.replace('Targets = ["b"] }', f'Targets = ["b"], Mode = "{mode}" }}', 1)


@pytest.mark.parametrize(("mode", "presses", "on"), [("once", 3, True), ("toggle", 2, False)])
def test_switch_modes(mode: str, presses: int, on: bool):
    rig = Rig(lever_mode(mode)).at(4)
    for _ in range(presses):
        rig.tick(Action.INTERACT).tick()
    assert rig.one("lever", Switch).on is on


def test_momentary_lever_is_on_while_held():
    rig = Rig(lever_mode("momentary")).at(4)
    rig.tick(Action.INTERACT).tick(Action.INTERACT)
    assert rig.one("door", Door).open
    rig.at(1).tick(Action.INTERACT)
    assert not rig.one("lever", Switch).on


def test_plate_holds_the_door_and_closing_waits_for_the_doorway():
    rig = Rig().at(10).tick()
    assert rig.one("pressure_plate", Switch).on
    assert rig.one("door", Door).open
    rig.at(7).tick()
    assert rig.one("door", Door).open
    rig.at(8.5).tick()
    assert not rig.one("door", Door).open
    assert rig.door_tile is Tile.SOLID


def test_all_and_invert_receivers():
    all_mode = TOML.replace('type = "Door"', 'type = "Door"\nfields = { Mode = "all" }')
    rig = Rig(all_mode).at(10).tick()
    assert not rig.one("door", Door).open
    inverted = TOML.replace('type = "Door"', 'type = "Door"\nfields = { Invert = true }')
    assert Rig(inverted).one("door", Door).open


def test_unloaded_sources_count_from_saved_state():
    rig = Rig()
    lever_iid = rig.one("lever", Identity).iid
    state = WorldState(entities={lever_iid: {"Switch": {"on": True}}})
    other = Rig(state=state)
    other.world.despawn(other.spawner.ids.pop(lever_iid))
    other.tick()
    assert other.one("door", Door).open


def test_pickups_are_collected_once():
    rig = Rig().at(13).tick()
    (collected,) = [e for e in rig.events if isinstance(e, Collected)]
    assert collected.value == 5
    assert collected.iid in rig.spawner.state.removed
    rig.tick()
    assert len([e for e in rig.events if isinstance(e, Collected)]) == 1


def test_dead_players_touch_nothing():
    rig = Rig()
    rig.motor.dead = True
    rig.at(10).tick()
    assert not rig.one("pressure_plate", Switch).on


def test_wiring_lists_sources_in_iid_order():
    rig = Rig()
    door, lever, plate = (rig.one(n, Identity).iid for n in ("door", "lever", "pressure_plate"))
    assert rig.world.resource(Wiring).sources == {door: sorted([lever, plate])}


def test_relighting_a_beacon_refills_the_dash_and_asks_for_a_save():
    rig = Rig().at(16).tick()
    rig.motor.dash_charges = 0
    rig.tick(Action.INTERACT)
    assert rig.one("beacon", Beacon).lit
    (lit,) = [e for e in rig.events if isinstance(e, BeaconLit)]
    assert (lit.iid, lit.room, lit.y) == (rig.one("beacon", Identity).iid, "Hall", FEET)
    assert rig.motor.dash_charges == 1
    rig.tick().tick(Action.INTERACT)
    assert len([e for e in rig.events if isinstance(e, BeaconLit)]) == 2
