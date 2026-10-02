"""Breakable walls, crates and pots, loose embers and crumbling platforms on a small world."""

from __future__ import annotations

import tomllib

import pytest
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import EntityId, Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, Tile, TileSource
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import Room, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner, WorldState
from emberwake.game import paths
from emberwake.game.actions import Action
from emberwake.game.breakables import (
    Breakable,
    BreakTuning,
    Broken,
    Crumble,
    Crumbled,
    LooseEmber,
    breakable_system,
    crumble_system,
    loose_ember_system,
)
from emberwake.game.combat import Hitbox, Team
from emberwake.game.interact import Collected
from emberwake.game.player.controller import Motor
from emberwake.game.player.swing import (
    Direction,
    Strikeable,
    Swing,
    SwingTuning,
    strike_system,
    swing_system,
)
from emberwake.game.player.tuning import PlayerTuning
from emberwake.game.scenes.gameplay import COLLISIONS

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
STEP = 1 / 60
TUNING = BreakTuning()
SWING = SwingTuning()
HALL = """
####################
#..................#
#..................#
#..................#
#..................#
######ff############
#...w..............#
#...w..............#
#...w..........zzz.#
#...w...c..o.......#
####################
"""
TOML = """
[entities.w]
type = "CrackedWall"
[entities.f]
type = "CrackedWall"
[entities.c]
type = "Crate"
fields = { Embers = 3 }
[entities.o]
type = "Pot"
[entities.z]
type = "CrumblingPlatform"
"""
FLOOR = 10 * 16
WALL_AT = (4, 7)
PLUG_AT = (6, 5)
CRATE_AT = (8, 9)
POT_AT = (11, 9)
PLATFORM_AT = (15, 8)


class Rig:
    def __init__(self, state: WorldState | None = None, tuning: BreakTuning = TUNING) -> None:
        level = _level()
        self.world = World()
        self.grid = WorldGrid()
        self.room = Room(level, level.layer("Collisions").to_tile_grid(COLLISIONS))
        self.grid.add(self.room)
        self.state = state or WorldState()
        self.spawner = Spawner(self.world, PREFABS, self.state)
        self.actions = InputState[Action]()
        self.bus = EventBus()
        self.broken: list[Broken] = []
        self.crumbled: list[Crumbled] = []
        self.collected: list[Collected] = []
        self.bus.subscribe(Broken, self.broken.append)
        self.bus.subscribe(Crumbled, self.crumbled.append)
        self.bus.subscribe(Collected, self.collected.append)
        for resource in (self.actions, self.bus, self.spawner, self.grid, tuning, SWING):
            self.world.insert_resource(resource)
        self.world.insert_resource(PlayerTuning())
        self.world.insert_resource(self.grid, key=TileSource)
        self.spawner.spawn_room(self.room)
        self.body = Body(40, FLOOR - 20, 10, 20)
        self.motor = Motor(grounded=True)
        self.player = self.world.spawn(self.body, self.motor, Swing(), Hitbox(targets=Team.ENEMY))
        self.schedule = Schedule(["logic", "post"])
        self.schedule.add("logic", swing_system)
        for system in (strike_system, breakable_system, crumble_system, loose_ember_system):
            self.schedule.add("post", system)
        self.tick()

    def tick(self, *held: Action, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.actions.advance(frozenset(held))
            self.schedule.run(self.world, STEP)
        return self

    def swing(self, *held: Action) -> Rig:
        """Press swing and run the whole swing."""
        self.tick(Action.SWING, *held)
        return self.tick(*held, ticks=SWING.length)

    def place(self, x: float, y: float, *, grounded: bool) -> Rig:
        self.body.x, self.body.y = x, y
        self.motor.grounded = grounded
        return self

    def at(self, cell: tuple[int, int]) -> Tile:
        return self.grid.get(*cell)

    def named(self, prefab: str) -> EntityId | None:
        for eid, identity in self.world.query(Identity):
            if identity.prefab == prefab and eid in self.world:
                return eid
        return None

    def crumble(self) -> Crumble:
        eid = self.named("crumbling_platform")
        assert eid is not None
        return self.world.get(eid, Crumble)

    def hit(self, prefab: str) -> Rig:
        """Break `prefab` right now, without a swing, so nothing else moves."""
        eid = self.named(prefab)
        assert eid is not None
        self.world.get(eid, Strikeable).struck = Direction.FORWARD
        breakable_system(self.world, STEP)
        self.world.flush()
        return self

    def count(self, prefab: str) -> int:
        return sum(1 for _, identity in self.world.query(Identity) if identity.prefab == prefab)

    def embers(self) -> list[Body]:
        return [body for _, body, _ in self.world.query(Body, LooseEmber)]

    def iid(self, prefab: str) -> str:
        eid = self.named(prefab)
        assert eid is not None
        return self.world.get(eid, Identity).iid


def _level():
    room_file = from_data(RoomFile, tomllib.loads(TOML))
    hall = make_room("Hall", (0, 0), HALL, room_file)
    return from_data(Project, build_project(Source(DEFS, [hall]))).levels[0]


def beside_wall(rig: Rig) -> Rig:
    return rig.place(3 * 16 + 1, FLOOR - 20, grounded=True)


def under_plug(rig: Rig) -> Rig:
    return rig.place(6 * 16 + 11, 100, grounded=False)


def over_plug(rig: Rig) -> Rig:
    return rig.place(6 * 16 + 11, 50, grounded=False)


def beside_crate(rig: Rig) -> Rig:
    return rig.place(7 * 16, FLOOR - 20, grounded=True)


def on_platform(rig: Rig) -> Rig:
    return rig.place(15 * 16 + 11, 8 * 16 - 20, grounded=True)


def test_walls_and_crates_are_solid_and_pots_are_not() -> None:
    rig = Rig()
    assert rig.at(WALL_AT) is Tile.SOLID
    assert rig.at((4, 9)) is Tile.SOLID
    assert rig.at(PLUG_AT) is Tile.SOLID
    assert rig.at(CRATE_AT) is Tile.SOLID
    assert rig.at(POT_AT) is Tile.EMPTY


def test_one_forward_swing_empties_a_cracked_wall() -> None:
    rig = beside_wall(Rig())
    rig.swing()
    assert [rig.at((4, row)) for row in range(6, 10)] == [Tile.EMPTY] * 4
    assert len(rig.broken) == 1
    assert rig.count("cracked_wall") == 1


def test_a_forward_swing_recoils_off_a_cracked_wall() -> None:
    rig = beside_wall(Rig())
    rig.tick(Action.SWING)
    rig.tick(ticks=SWING.windup)
    assert rig.motor.vx == -SWING.recoil


def test_an_up_swing_breaks_the_ceiling_above() -> None:
    rig = under_plug(Rig())
    rig.swing(Action.UP)
    assert rig.at(PLUG_AT) is Tile.EMPTY
    assert rig.at((7, 5)) is Tile.EMPTY


def test_a_down_swing_breaks_the_floor_below_without_a_pogo() -> None:
    rig = over_plug(Rig())
    rig.tick(Action.SWING, Action.DOWN)
    rig.tick(Action.DOWN, ticks=SWING.windup)
    assert rig.at(PLUG_AT) is Tile.EMPTY
    assert rig.motor.vy >= 0
    assert rig.motor.dash_charges == Motor().dash_charges


def test_one_swing_breaks_what_it_touches_once() -> None:
    rig = beside_wall(Rig())
    rig.swing()
    assert len(rig.broken) == 1


def test_a_crate_breaks_into_its_embers_and_a_pot_into_one() -> None:
    rig = Rig().hit("crate")
    assert rig.at(CRATE_AT) is Tile.EMPTY
    assert len(rig.embers()) == 3
    rig.hit("pot")
    assert len(rig.embers()) == 4
    assert len(rig.broken) == 2


def test_breaking_is_retired_by_iid_and_never_spawns_again() -> None:
    rig = beside_crate(Rig())
    iid = rig.iid("crate")
    rig.swing()
    assert iid in rig.state.removed
    again = Rig(rig.state)
    assert again.named("crate") is None
    assert again.at(CRATE_AT) is Tile.EMPTY
    again.spawner.spawn_room(again.room)
    again.tick()
    assert again.named("crate") is None


def test_a_broken_wall_stays_open_when_its_room_reloads() -> None:
    rig = beside_wall(Rig())
    rig.swing()
    again = Rig(rig.state)
    assert again.at(WALL_AT) is Tile.EMPTY
    assert again.count("cracked_wall") == 1
    assert again.named("crate") is not None


def test_unbroken_things_come_back_with_their_room() -> None:
    rig = beside_wall(Rig())
    rig.swing()
    again = Rig(rig.state)
    assert again.at(PLUG_AT) is Tile.SOLID
    assert again.at(CRATE_AT) is Tile.SOLID


def _flung(rig: Rig) -> list[tuple[float, float]]:
    rig.hit("crate")
    return [(ember.vx, ember.vy) for _, _, ember in rig.world.query(Body, LooseEmber)]


def test_a_crate_flings_its_embers_the_same_way_every_time() -> None:
    assert _flung(Rig()) == _flung(Rig())


def test_embers_scatter_upward_within_the_speed_range() -> None:
    low, high = TUNING.ember_speed
    for vx, vy in _flung(Rig()):
        assert vy < 0
        assert low <= (vx * vx + vy * vy) ** 0.5 <= high + 1e-6


def test_embers_fall_until_they_settle_then_stop_falling_and_home_in() -> None:
    rig = Rig().hit("crate")
    rig.place(2 * 16, 30, grounded=False)
    (first, *_) = [ember for _, _, ember in rig.world.query(Body, LooseEmber)]
    before = first.vy
    rig.tick(ticks=3)
    assert first.vy != before
    rig.tick(ticks=int(TUNING.ember_settle / STEP))
    settled = first.vy
    rig.tick(ticks=3)
    assert first.vy == settled
    assert not rig.collected


def test_loose_embers_home_in_through_walls_and_are_collected() -> None:
    rig = Rig().hit("crate")
    iid = rig.broken[0].iid
    rig.place(2 * 16, 30, grounded=False)
    rig.tick(ticks=240)
    assert rig.embers() == []
    assert rig.collected == [Collected(iid, 1)] * 3


def test_a_platform_holds_the_player_then_clears_after_the_delay() -> None:
    rig = on_platform(Rig())
    assert rig.at(PLATFORM_AT) is Tile.ONE_WAY
    rig.tick()
    state = rig.crumble()
    assert state.state == "shaking"
    rig.tick(ticks=int(TUNING.crumble_delay / STEP) - 2)
    assert rig.at(PLATFORM_AT) is Tile.ONE_WAY
    assert not rig.crumbled
    rig.tick(ticks=3)
    assert state.state == "gone"
    assert [rig.at((col, 8)) for col in (15, 16, 17)] == [Tile.EMPTY] * 3
    assert len(rig.crumbled) == 1


def test_a_platform_comes_back_after_the_return_time() -> None:
    rig = on_platform(Rig())
    rig.tick(ticks=int(TUNING.crumble_delay / STEP) + 2)
    rig.place(3 * 16, FLOOR - 20, grounded=True)
    rig.tick(ticks=int(TUNING.crumble_return / STEP) - 2)
    assert rig.at(PLATFORM_AT) is Tile.EMPTY
    rig.tick(ticks=4)
    assert rig.at(PLATFORM_AT) is Tile.ONE_WAY


def test_a_platform_does_not_come_back_while_the_player_overlaps_it() -> None:
    rig = on_platform(Rig())
    rig.tick(ticks=int(TUNING.crumble_delay / STEP) + 2)
    rig.place(15 * 16 + 11, 8 * 16 - 4, grounded=False)
    rig.tick(ticks=int(TUNING.crumble_return / STEP) + 30)
    assert rig.at(PLATFORM_AT) is Tile.EMPTY
    rig.place(3 * 16, FLOOR - 20, grounded=True)
    rig.tick()
    assert rig.at(PLATFORM_AT) is Tile.ONE_WAY


def test_only_a_player_standing_on_it_sets_a_platform_off() -> None:
    rig = Rig()
    rig.tick(ticks=120)
    assert rig.crumble().state == "whole"
    rig.place(15 * 16 + 11, 8 * 16 - 60, grounded=False)
    rig.tick(ticks=120)
    assert rig.crumble().state == "whole"


def test_a_platform_that_reloads_is_whole() -> None:
    rig = on_platform(Rig())
    rig.tick(ticks=int(TUNING.crumble_delay / STEP) + 2)
    again = Rig(rig.state)
    assert again.at(PLATFORM_AT) is Tile.ONE_WAY
    assert again.crumble().state == "whole"


def test_strikeables_that_are_not_breakable_are_left_alone() -> None:
    rig = beside_wall(Rig())
    other = rig.world.spawn(Body(55, FLOOR - 16, 16, 16), Strikeable())
    rig.swing()
    assert other in rig.world
    assert rig.world.find(other, Breakable) is None


@pytest.mark.parametrize("direction", [Direction.FORWARD, Direction.UP, Direction.DOWN])
def test_any_direction_breaks_a_breakable(direction: Direction) -> None:
    rig = Rig()
    eid = rig.named("pot")
    assert eid is not None
    rig.world.get(eid, Strikeable).struck = direction
    breakable_system(rig.world, STEP)
    assert len(rig.broken) == 1
