"""Lifts and platforms on a small world: wiring, loops, carrying, holding and persistence."""

from __future__ import annotations

import tomllib

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, TileSource
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import Room, WorldGrid
from emberwake.engine.world.spawning import Spawner, WorldState
from emberwake.game import paths
from emberwake.game.actions import Action
from emberwake.game.crates import CrateTuning, PushCrate, crate_system
from emberwake.game.flags import Facts
from emberwake.game.interact import Switch
from emberwake.game.platforms import Platform, PlatformRest, PlatformTuning, platform_system
from emberwake.game.player.controller import Motor, PlayerState
from emberwake.game.player.system import player_system
from emberwake.game.player.tuning import PlayerTuning
from emberwake.game.scenes.gameplay import COLLISIONS
from emberwake.game.signals import Wiring, signal_system

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
STEP = 1 / 60
SPEED = PlatformTuning().speed * STEP
"""px per tick."""
FLOOR = 10 * 16

LIFT = """
####################
#..................#
#..................#
#..................#
#..n...............#
#..................#
#..................#
#..................#
#..c...............#
#..LLL..l..........#
####################
"""
CEILING = LIFT.replace("#..n...............#", "#..................#").replace(
    "#..................#\n#..................#\n#..................#\n#..................#\n#..c",
    "#..................#\n#..................#\n#..n...............#\n#..................#\n#..c",
)
ACROSS = """
####################
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..LLL.........n...#
####################
"""
DROP = """
####################
#..................#
#..LLL.............#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..n..........l....#
####################
"""
LOW = """
####################
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
####################
"""

WIRED = """
[entities.L]
type = "Platform"
fields = { Path = ["n"] }
[entities.n]
type = "PathNode"
[entities.l]
type = "Lever"
fields = { Targets = ["L"] }
[entities.c]
type = "PushCrate"
"""
LOOP = WIRED.replace('[entities.l]\ntype = "Lever"\nfields = { Targets = ["L"] }\n', "")


def _level(hall: str, toml: str):
    data = tomllib.loads(toml)
    data["entities"] = {key: spec for key, spec in data["entities"].items() if key in hall}
    room_file = from_data(RoomFile, data)
    room = make_room("Hall", (0, 0), hall, room_file)
    return from_data(Project, build_project(Source(DEFS, [room]))).levels[0]


class Rig:
    def __init__(self, hall: str = LIFT, toml: str = WIRED) -> None:
        level = _level(hall, toml)
        self.world = World()
        self.grid = WorldGrid()
        self.room = Room(level, level.layer("Collisions").to_tile_grid(COLLISIONS))
        self.grid.add(self.room)
        self.state = WorldState()
        self.spawner = Spawner(self.world, PREFABS, self.state)
        self.actions = InputState[Action]()
        wiring = Wiring.from_levels([level], PREFABS)
        facts = Facts({}, [], {})
        tunings = (CrateTuning(), PlatformTuning(), PlayerTuning())
        resources = (self.actions, EventBus(), self.spawner, self.grid, wiring, facts, *tunings)
        for resource in resources:
            self.world.insert_resource(resource)
        self.world.insert_resource(self.grid, key=TileSource)
        self.spawner.spawn_room(self.room)
        self.world.flush()
        self.body = Body(0.0, 0.0, 10, 20)
        self.motor = Motor(grounded=True)
        self.world.spawn(self.body, self.motor)
        self.stand_on_floor()
        self.schedule = Schedule(["physics", "post"])
        for system in (platform_system, player_system, crate_system):
            self.schedule.add("physics", system)
        self.schedule.add("post", signal_system)
        self.tick(ticks=2)

    def tick(self, *held: Action, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.actions.advance(frozenset(held))
            self.schedule.run(self.world, STEP)
        return self

    @property
    def platform(self) -> Body:
        return next(body for _, body, _ in self.world.query(Body, Platform))

    @property
    def crate(self) -> Body:
        return next(body for _, body, _ in self.world.query(Body, PushCrate))

    def rest(self) -> PlatformRest:
        return next(rest for _, rest in self.world.query(PlatformRest))

    def power(self, on: bool = True) -> Rig:
        next(switch for _, switch in self.world.query(Switch)).on = on
        return self

    def stand_on_floor(self, x: float = 16.0) -> None:
        self.put(x, FLOOR - 20)

    def put(self, x: float, y: float) -> None:
        self.body.x, self.body.y = x, y
        self.motor.vx = self.motor.vy = 0.0
        self.motor.grounded = True

    def ride(self, inset: float = 20.0) -> Rig:
        top = self.platform
        self.put(top.x + inset, top.y - 20)
        return self

    def reload(self) -> Rig:
        self.spawner.despawn_room(self.room)
        self.world.flush()
        self.spawner.spawn_room(self.room)
        return self.tick(ticks=2)


def test_a_powered_lift_travels_to_its_node_at_speed_and_stays():
    rig = Rig().power().tick()
    home = rig.platform.y
    rig.tick(ticks=30)
    assert abs((home - rig.platform.y) - 30 * SPEED) < 1e-6
    rig.tick(ticks=200)
    assert (rig.platform.x, rig.platform.y) == (3 * 16, 4 * 16)
    rig.tick(ticks=50)
    assert rig.platform.y == 4 * 16


def test_an_unpowered_lift_returns_home_and_stays():
    rig = Rig().power().tick(ticks=60)
    rig.power(False).tick(ticks=400)
    assert (rig.platform.x, rig.platform.y) == (3 * 16, 9 * 16)


def test_a_lift_switched_back_half_way_turns_round():
    rig = Rig().power().tick(ticks=40)
    mid = rig.platform.y
    rig.power(False).tick(ticks=20)
    assert mid < rig.platform.y < 9 * 16


def test_a_lift_with_no_power_does_not_move():
    rig = Rig().tick(ticks=60)
    assert rig.platform.y == 9 * 16


def test_an_unwired_platform_loops_and_rests_at_each_end():
    rig = Rig(ACROSS, LOOP)
    dwell = PlatformTuning().dwell
    travel = round((12 * 16) / SPEED)
    rig.tick(ticks=travel - 10)
    assert rig.platform.x < 15 * 16
    rig.tick(ticks=12)
    assert rig.platform.x == 15 * 16
    rig.tick(ticks=round(dwell / STEP) - 8)
    assert rig.platform.x == 15 * 16
    rig.tick(ticks=15)
    assert rig.platform.x < 15 * 16
    rig.tick(ticks=travel * 2)
    assert 3 * 16 <= rig.platform.x <= 15 * 16


def test_the_player_standing_on_a_lift_is_carried_up_and_down():
    rig = Rig().power().ride()
    rig.tick(ticks=40)
    assert rig.motor.grounded
    assert rig.body.bottom == rig.platform.y
    assert rig.platform.y < 9 * 16 - 20
    rig.power(False).tick(ticks=40)
    assert rig.body.bottom == rig.platform.y
    assert rig.motor.grounded


def test_the_player_is_carried_sideways():
    rig = Rig(ACROSS, LOOP).ride(0.0)
    rig.put(rig.platform.x + 20, rig.platform.y - 20)
    start = rig.body.x
    rig.tick(ticks=60)
    assert abs(rig.body.x - start - 60 * SPEED) < 0.05
    assert rig.body.bottom == rig.platform.y


def test_the_player_can_jump_from_a_platform_and_is_not_carried_after():
    rig = Rig(ACROSS, LOOP).ride(0.0)
    rig.put(rig.platform.x + 20, rig.platform.y - 20)
    rig.tick(Action.JUMP, ticks=3)
    start = rig.body.x
    rig.tick(ticks=8)
    assert rig.body.x == start
    assert rig.platform.x - 3 * 16 > 10 * SPEED


def test_the_player_slides_down_the_side_of_a_platform():
    rig = Rig().tick()
    rig.put(48 - 10.0, 150 - 20.0)
    rig.motor.grounded = False
    rig.motor.vy = 200.0
    rig.tick(Action.RIGHT)
    assert rig.motor.state is PlayerState.WALL_SLIDE
    assert rig.body.x + rig.body.width == 48


def test_a_crate_and_a_crate_on_it_ride_a_lift():
    rig = Rig().power().tick(ticks=60)
    assert rig.platform.y < 9 * 16 - 40
    assert rig.crate.bottom == rig.platform.y


def test_a_player_standing_on_a_crate_on_a_lift_is_carried_too():
    rig = Rig().power()
    rig.crate.x = rig.platform.x + 16
    rig.tick(ticks=2)
    rig.put(rig.crate.x + 3, rig.crate.y - 20)
    rig.tick(ticks=60)
    assert rig.body.bottom == rig.crate.y
    assert rig.crate.bottom == rig.platform.y


def test_the_player_is_stood_on_not_inside_a_platform_that_moves_up():
    rig = Rig().power().ride().tick(ticks=60)
    assert rig.body.bottom <= rig.platform.y + 1e-6
    assert not (rig.body.y < rig.platform.bottom and rig.platform.y < rig.body.bottom - 1e-3)


def test_a_platform_holds_above_a_player_and_goes_on_when_they_leave():
    rig = Rig(DROP, WIRED).power()
    rig.put(3 * 16 + 3, FLOOR - 20)
    rig.tick(ticks=300)
    assert abs(rig.platform.bottom - (FLOOR - 20)) < 1e-3
    assert (rig.body.x, rig.body.y) == (3 * 16 + 3, FLOOR - 20)
    rig.put(12 * 16, FLOOR - 20)
    rig.tick(ticks=100)
    assert abs(rig.platform.y - 9 * 16) < 1e-3


def test_a_platform_does_not_sweep_into_a_player_beside_it():
    rig = Rig(ACROSS, LOOP)
    rig.put(10 * 16, FLOOR - 20)
    rig.tick(ticks=400)
    assert rig.platform.x + rig.platform.width <= 10 * 16 + 1e-6
    assert (rig.body.x, rig.body.y) == (10 * 16, FLOOR - 20)
    rig.put(1 * 16, FLOOR - 20)
    rig.tick(ticks=100)
    assert rig.platform.x > 10 * 16 - 48 + 40


def test_a_rider_is_not_crushed_against_a_ceiling():
    rig = Rig(CEILING).power().ride()
    rig.tick(ticks=300)
    assert rig.body.y >= 16 - 1e-6
    assert rig.body.bottom <= rig.platform.y + 1e-6
    assert rig.platform.y >= 16 + 20 - 1e-6


def test_where_a_platform_is_survives_its_room_reloading():
    rig = Rig().power().tick(ticks=45)
    left, s = rig.platform.y, rig.rest().s
    rig.reload()
    assert abs(rig.platform.y - left) < SPEED
    assert abs(rig.rest().s - s) < 2 * SPEED


def test_a_saved_platform_is_in_place_as_soon_as_it_spawns():
    rig = Rig().power().tick(ticks=45)
    left = rig.platform.y
    rig.spawner.despawn_room(rig.room)
    rig.world.flush()
    rig.spawner.spawn_room(rig.room)
    rig.world.flush()
    assert rig.platform.y == 9 * 16
    platform_system(rig.world, STEP)
    assert abs(rig.platform.y - left) < SPEED


def test_the_same_input_leaves_platforms_and_riders_in_the_same_places():
    def play() -> list[tuple[float, float]]:
        rig = Rig().power().ride()
        for held in ([Action.RIGHT] * 20, [Action.JUMP] * 3, [Action.LEFT] * 40, [None] * 100):
            for action in held:
                rig.tick(*([action] if action else []))
        return [(b.x, b.y) for _, b, _ in rig.world.query(Body, Platform)] + [
            (rig.body.x, rig.body.y),
            (rig.crate.x, rig.crate.y),
        ]

    assert play() == play()
