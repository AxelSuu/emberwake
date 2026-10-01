from __future__ import annotations

import pytest

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import World
from emberwake.engine.physics import Body, Tile, TileGrid
from emberwake.engine.world.rooms import WorldGrid
from emberwake.game.beacons import Beacon
from emberwake.game.combat import Damaged, Health, Killed
from emberwake.game.light import (
    Ember,
    Lightform,
    LightSource,
    LightTuning,
    ember_system,
    falloff,
    lantern_reach,
    light_at,
    lightform_system,
)
from emberwake.game.player.controller import Motor

TUNING = LightTuning(ember_max=100, drain=10, refill=20, lantern_radius=40, beacon_radius=80)


class Cave:
    def __init__(self) -> None:
        self.world = World()
        self.bus = EventBus()
        self.hurts: list[Damaged] = []
        self.deaths: list[Killed] = []
        self.bus.subscribe(Damaged, self.hurts.append)
        self.bus.subscribe(Killed, self.deaths.append)
        grid = TileGrid(20, 10, 16, bytearray(200))
        self.grid = grid
        self.world.insert_resource(TUNING)
        self.world.insert_resource(self.bus)
        self.world.insert_resource(grid, key=WorldGrid)
        self.player = self.world.spawn(
            Body(100, 100, 14, 22), Motor(), Ember(100), Health(2, iframes=0.0)
        )
        self.world.flush()

    def add(self, *parts: object) -> None:
        self.world.spawn(*parts)
        self.world.flush()

    def ember(self) -> Ember:
        return self.world.get(self.player, Ember)

    def move_player(self, x: float, y: float) -> None:
        body = self.world.get(self.player, Body)
        body.x, body.y = x, y

    def tick(self, seconds: float = 1.0) -> None:
        ember_system(self.world, seconds)
        lightform_system(self.world, seconds)
        self.world.flush()


def test_falloff_is_linear_to_the_radius() -> None:
    assert falloff(0, 50) == 1
    assert falloff(25, 50) == pytest.approx(0.5)
    assert falloff(50, 50) == 0
    assert falloff(10, 50, strength=0.5) == pytest.approx(0.4)


def test_darkness_drains_the_ember() -> None:
    cave = Cave()
    cave.tick(2.0)
    assert cave.ember().current == pytest.approx(80)
    assert not cave.ember().in_light


def test_the_players_own_lantern_does_not_refill() -> None:
    cave = Cave()
    assert light_at(cave.world, 107, 111) == 1
    assert light_at(cave.world, 107, 111, lantern=False) == 0
    cave.tick()
    assert cave.ember().current < 100


def test_lit_beacon_refills_and_unlit_does_not() -> None:
    cave = Cave()
    cave.ember().current = 50
    cave.add(Body(100, 100, 14, 22), Beacon(lit=False))
    cave.tick()
    assert cave.ember().current == pytest.approx(40)
    cave.ember().current = 10
    cave.add(Body(100, 100, 14, 22), Beacon(lit=True))
    cave.tick()
    assert cave.ember().current == pytest.approx(30)
    assert cave.ember().in_light


def test_brazier_range_is_bounded() -> None:
    cave = Cave()
    cave.add(Body(0, 100, 16, 16), LightSource(radius=50))
    cave.ember().current = 50
    cave.tick(1.0)
    assert cave.ember().current == pytest.approx(40)
    cave.move_player(20, 100)
    cave.tick(1.0)
    assert cave.ember().current == pytest.approx(60)


def test_ember_is_capped() -> None:
    cave = Cave()
    cave.add(Body(100, 100, 14, 22), Beacon(lit=True))
    cave.tick(10)
    assert cave.ember().current == 100


def test_an_empty_flame_gutters_and_costs_health_every_few_seconds() -> None:
    cave = Cave()
    cave.ember().current = 5
    cave.tick(1.0)
    assert cave.ember().guttering
    assert not cave.hurts
    cave.tick(TUNING.gutter_every)
    assert [hurt.amount for hurt in cave.hurts] == [1]
    assert not cave.deaths
    cave.tick(TUNING.gutter_every)
    assert len(cave.deaths) == 1


def test_the_lantern_shrinks_while_guttering_and_light_ends_it() -> None:
    cave = Cave()
    assert lantern_reach(cave.world) == TUNING.lantern_radius
    cave.ember().current = 0
    cave.tick(0.5)
    assert lantern_reach(cave.world) == TUNING.lantern_radius * TUNING.gutter_radius
    cave.add(Body(100, 100, 8, 8), LightSource(radius=60))
    cave.tick(0.5)
    assert not cave.ember().guttering
    assert cave.ember().gutter == 0


def test_lightform_is_solid_only_while_lit() -> None:
    cave = Cave()
    cave.add(Body(32, 64, 32, 8), Lightform())
    cave.move_player(300, 100)
    cave.tick()
    assert cave.grid.get(2, 4) is Tile.EMPTY
    cave.add(Body(40, 40, 8, 8), LightSource(radius=60))
    cave.tick()
    assert cave.grid.get(2, 4) is Tile.ONE_WAY
    assert cave.grid.get(3, 4) is Tile.ONE_WAY
    assert cave.grid.get(4, 4) is Tile.EMPTY


def test_the_lantern_can_light_a_lightform() -> None:
    cave = Cave()
    cave.add(Body(100, 120, 32, 8), Lightform())
    cave.tick()
    assert cave.grid.get(6, 7) is Tile.ONE_WAY
    cave.move_player(300, 100)
    cave.tick()
    assert cave.grid.get(6, 7) is Tile.EMPTY


def test_dead_players_do_not_drain() -> None:
    cave = Cave()
    cave.world.get(cave.player, Motor).dead = True
    cave.tick(3.0)
    assert cave.ember().current == 100
