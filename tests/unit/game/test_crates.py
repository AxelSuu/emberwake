"""Push crates on a small world: pushing, falling, stacking, plates, persistence and rest."""

from __future__ import annotations

import tomllib

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import EntityId, Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, TileSource
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import Room, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner, WorldState
from emberwake.game import paths
from emberwake.game.actions import Action
from emberwake.game.crates import (
    CrateRest,
    CrateTuning,
    PushCrate,
    crate_system,
    reset_crates,
)
from emberwake.game.interact import Switch, plate_system, trigger_system
from emberwake.game.player.controller import Motor
from emberwake.game.player.system import player_system
from emberwake.game.player.tuning import PlayerTuning
from emberwake.game.scenes.gameplay import COLLISIONS

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
STEP = 1 / 60
TUNING = CrateTuning()
HALL = """
####################
#..................#
#.o................#
#..................#
#................t.#
#..................#
#.====.............#
#..................#
#..................#
#...c....p..f..s...#
####################
"""
TOML = """
[entities.c]
type = "PushCrate"
[entities.o]
type = "PushCrate"
[entities.t]
type = "PushCrate"
[entities.f]
type = "PushCrate"
[entities.s]
type = "PushCrate"
[entities.p]
type = "PressurePlate"
"""
AT = {"c": (4, 9), "o": (2, 2), "t": (17, 4), "f": (12, 9), "s": (15, 9), "p": (9, 9)}
FLOOR = 10 * 16
PLATE = 9 * 16
"""Left edge of the plate."""


class Rig:
    def __init__(self, state: WorldState | None = None) -> None:
        level = _level()
        self.world = World()
        self.grid = WorldGrid()
        self.room = Room(level, level.layer("Collisions").to_tile_grid(COLLISIONS))
        self.grid.add(self.room)
        self.state = state or WorldState()
        self.spawner = Spawner(self.world, PREFABS, self.state)
        self.actions = InputState[Action]()
        for resource in (self.actions, EventBus(), self.spawner, self.grid, TUNING, PlayerTuning()):
            self.world.insert_resource(resource)
        self.world.insert_resource(self.grid, key=TileSource)
        self.spawner.spawn_room(self.room)
        self.world.flush()
        self.iids = {m: self.world.get(e, Identity).iid for m, e in self.find().items()}
        self.body = Body(2 * 16, FLOOR - 20, 10, 20)
        self.motor = Motor(grounded=True)
        self.player = self.world.spawn(self.body, self.motor)
        self.schedule = Schedule(["physics", "post"])
        for system in (player_system, crate_system):
            self.schedule.add("physics", system)
        for system in (trigger_system, plate_system):
            self.schedule.add("post", system)
        self.tick(ticks=2)

    def tick(self, *held: Action, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.actions.advance(frozenset(held))
            self.schedule.run(self.world, STEP)
        return self

    def find(self) -> dict[str, EntityId]:
        """Entities by marker, told apart by where the level placed them."""
        spots = {(16.0 * column, 16.0 * row): marker for marker, (column, row) in AT.items()}
        return {
            spots[body.x, body.y]: eid
            for eid, body, _ in self.world.query(Body, Identity)
            if (body.x, body.y) in spots
        }

    def eid(self, marker: str) -> EntityId:
        eid = self.spawner.resolve(self.iids[marker])
        assert eid is not None
        return eid

    def crate(self, marker: str) -> Body:
        return self.world.get(self.eid(marker), Body)

    def plate_on(self) -> bool:
        return self.world.get(self.eid("p"), Switch).on

    def stand(self, x: float, y: float | None = None) -> Rig:
        self.body.x, self.body.y = x, FLOOR - 20 if y is None else y
        self.motor.vx = self.motor.vy = 0.0
        self.motor.grounded = True
        return self

    def reload(self) -> Rig:
        self.spawner.despawn_room(self.room)
        self.world.flush()
        self.spawner.spawn_room(self.room)
        return self.tick(ticks=2)


def _level():
    room_file = from_data(RoomFile, tomllib.loads(TOML))
    hall = make_room("Hall", (0, 0), HALL, room_file)
    return from_data(Project, build_project(Source(DEFS, [hall]))).levels[0]


def settled(rig: Rig) -> Rig:
    return rig.tick(ticks=90)


def test_crates_fall_and_rest_on_the_floor_a_one_way_and_each_other():
    rig = settled(Rig())
    assert rig.crate("f").bottom == FLOOR
    assert rig.crate("o").bottom == 6 * 16
    assert rig.crate("o").x == 2 * 16
    stack = rig.crate("t"), rig.crate("s")
    assert (stack[0].x, stack[1].x) == (17 * 16, 15 * 16)


def test_a_dropped_crate_lands_on_the_one_below_it():
    rig = Rig()
    rig.crate("t").x = rig.crate("s").x
    settled(rig)
    assert rig.crate("s").bottom == FLOOR
    assert rig.crate("t").bottom == rig.crate("s").y


def test_the_player_stands_on_a_crate_and_jumps_from_it():
    rig = settled(Rig())
    top = rig.crate("c")
    rig.stand(top.x + 3, top.y - 20).tick(ticks=10)
    assert rig.motor.grounded
    assert rig.body.bottom == top.y
    rig.tick(Action.JUMP, ticks=6)
    assert rig.body.bottom < top.y - 4


def test_walking_into_a_crate_pushes_it_at_push_speed_and_the_player_keeps_pace():
    rig = settled(Rig())
    start = rig.crate("c").x
    rig.stand(start - 30).tick(Action.RIGHT, ticks=60)
    crate = rig.crate("c")
    assert crate.x - (rig.body.x + rig.body.width) <= TUNING.push_speed * STEP
    moved = crate.x - start
    assert 0 < moved <= TUNING.push_speed * 1.0
    assert moved > TUNING.push_speed * 0.5
    before = crate.x
    rig.tick(Action.RIGHT, ticks=30)
    assert abs(rig.crate("c").x - before - TUNING.push_speed * 0.5) < 1.0


def test_walking_away_or_through_the_air_does_not_move_a_crate():
    rig = settled(Rig())
    start = rig.crate("c").x
    rig.stand(start + 16 + 0.1).tick(Action.RIGHT, ticks=20)
    assert rig.crate("c").x == start
    rig.stand(start - 10.0, FLOOR - 70).tick(Action.RIGHT, ticks=3)
    assert rig.crate("c").x == start


def test_a_crate_against_another_crate_does_not_move_and_stops_the_player():
    rig = settled(Rig())
    rig.crate("f").x = rig.crate("s").x - 16
    rig.stand(rig.crate("f").x - 10.0).tick(Action.RIGHT, ticks=40)
    assert rig.crate("f").x + 16 == rig.crate("s").x - 0
    assert rig.crate("s").x == 15 * 16
    assert rig.body.x + rig.body.width == rig.crate("f").x


def test_a_crate_pushed_off_a_ledge_falls():
    rig = Rig()
    rig.crate("o").x = 4 * 16
    settled(rig)
    ledge = rig.crate("o")
    assert ledge.bottom == 6 * 16
    rig.stand(ledge.x - 10.0, ledge.bottom - 20.0).tick(Action.RIGHT, ticks=150)
    assert rig.crate("o").x > 6 * 16
    assert rig.crate("o").bottom == FLOOR


def test_a_crate_over_a_plate_holds_it_down_with_the_player_away():
    rig = settled(Rig())
    assert not rig.plate_on()
    rig.crate("c").x = PLATE + 2
    rig.stand(2 * 16).tick(ticks=5)
    assert rig.plate_on()
    assert rig.world.get(rig.player, Body).x == 2 * 16


def test_a_crate_barely_on_the_plate_does_not_press_it():
    rig = settled(Rig())
    rig.crate("c").x = PLATE - 12
    rig.tick(ticks=3)
    assert not rig.plate_on()
    rig.crate("c").x = PLATE - 8
    rig.tick(ticks=3)
    assert rig.plate_on()


def test_pushing_a_crate_off_the_plate_releases_it():
    rig = settled(Rig())
    rig.crate("c").x = PLATE
    rig.stand(PLATE - 20.0).tick(Action.RIGHT, ticks=120)
    assert not rig.plate_on()


def test_where_a_crate_was_left_survives_its_room_reloading():
    rig = settled(Rig())
    start = rig.crate("c").x
    rig.stand(start - 30).tick(Action.RIGHT, ticks=60)
    left = rig.crate("c").x
    assert left > start
    rig.reload()
    assert rig.crate("c").x == left


def test_a_saved_crate_is_in_place_as_soon_as_it_spawns():
    rig = settled(Rig())
    rig.crate("c").x += 32
    rig.tick()
    saved = rig.crate("c").x
    rig.spawner.despawn_room(rig.room)
    rig.world.flush()
    rig.spawner.spawn_room(rig.room)
    rig.world.flush()
    assert rig.crate("c").x != saved
    crate_system(rig.world, STEP)
    assert rig.crate("c").x == saved


def test_resting_sends_crates_home_live_and_unloaded():
    rig = settled(Rig())
    home = rig.crate("c").x
    rig.crate("c").x += 48
    rig.tick()
    rig.spawner.snapshot_all()
    assert "CrateRest" in rig.state.entities[next(i for i in rig.state.entities if i.endswith("c"))]
    reset_crates(rig.world, rig.state)
    assert rig.crate("c").x == home
    assert not any("CrateRest" in saved for saved in rig.state.entities.values())
    rig.spawner.despawn_room(rig.room)
    rig.world.flush()
    rig.spawner.spawn_room(rig.room)
    rig.tick(ticks=2)
    assert rig.crate("c").x == home


def test_a_crate_that_falls_out_of_the_world_is_home_again():
    rig = settled(Rig())
    home = rig.crate("c").x, rig.crate("c").y
    rig.crate("c").y = 4000.0
    rig.tick()
    assert (rig.crate("c").x, rig.crate("c").y) == home
    assert rig.world.get(rig.eid("c"), PushCrate).vy == 0.0


def test_a_crate_pushed_into_a_wall_stops_there_and_stops_the_player():
    rig = settled(Rig())
    rig.crate("c").x = 40.0
    rig.stand(40.0 + 16 + 0.1).tick(Action.LEFT, ticks=80)
    assert rig.crate("c").x == 16
    assert rig.body.x == 32


def test_the_same_input_leaves_crates_in_the_same_places():
    def play() -> list[tuple[float, float]]:
        rig = settled(Rig())
        rig.stand(rig.crate("c").x - 30)
        for held in ([Action.RIGHT] * 200, [Action.JUMP, Action.RIGHT] * 40, [Action.LEFT] * 60):
            for action in held:
                rig.tick(action)
        return [(b.x, b.y) for _, b, _, _ in rig.world.query(Body, PushCrate, CrateRest)]

    assert play() == play()
