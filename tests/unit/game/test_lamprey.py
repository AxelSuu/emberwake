from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.physics import Body, Tile, TileGrid
from emberwake.engine.world.rooms import WorldGrid
from emberwake.game.combat import Guard, Health, Hitbox, Hurtbox, Team, combat_system
from emberwake.game.flares import Flare
from emberwake.game.lamprey import (
    MODES,
    Ctx,
    Lamprey,
    LampreyTuning,
    PhaseChanged,
    brightest,
    phase_for,
)
from emberwake.game.lamprey_system import lamprey_system
from emberwake.game.lamps import Lamp
from emberwake.game.light import LightSource, LightTuning
from emberwake.game.player.controller import Motor

STEP = 1 / 60
TILE = 16
WATER = 17 * TILE
"""Water line of the test arena, px."""
TUNING = LampreyTuning()


class Arena:
    """A 40x22 tile room, stone all round, with the water line at row 17."""

    def __init__(self) -> None:
        self.world = World()
        grid = TileGrid(40, 22, TILE, bytearray(40 * 22))
        for column in range(40):
            grid.set(column, 0, Tile.SOLID)
            grid.set(column, 21, Tile.SOLID)
        for row in range(22):
            grid.set(0, row, Tile.SOLID)
            grid.set(39, row, Tile.SOLID)
        self.grid = grid
        self.bus = EventBus()
        self.phases: list[PhaseChanged] = []
        self.bus.subscribe(PhaseChanged, self.phases.append)
        for resource in (TUNING, LightTuning(), self.bus):
            self.world.insert_resource(resource)
        self.world.insert_resource(grid, key=WorldGrid)
        self.boss = self.world.spawn(Body(18 * TILE, WATER - 16, 32, 16), Lamprey())
        self.world.flush()
        self.player = self.world.spawn(Body(3 * TILE, WATER - 36, 10, 20), Motor(), Health(3))
        self.world.flush()
        self.tick()

    def tick(self, seconds: float = STEP) -> None:
        for _ in range(max(1, round(seconds / STEP))):
            lamprey_system(self.world, STEP)
            combat_system(self.world, STEP)
            self.world.flush()

    def ctx(self) -> Ctx:
        return Ctx(
            self.world,
            self.boss,
            self.world.get(self.boss, Body),
            self.state,
            TUNING,
            self.world.resource(WorldGrid),
            self.world.get(self.player, Body),
        )

    @property
    def state(self) -> Lamprey:
        return self.world.get(self.boss, Lamprey)

    @property
    def health(self) -> Health:
        return self.world.get(self.boss, Health)

    def lamp(self, x: float, *, lit: bool = True) -> EntityId:
        eid = self.world.spawn(Body(x - 8, WATER - 80, 16, 32), Lamp(lit=lit))
        self.world.flush()
        return eid

    def flare(self, x: float, y: float, strength: float = 1.0) -> EntityId:
        eid = self.world.spawn(Body(x - 3, y - 3, 6, 6), Flare(), LightSource(strength=strength))
        self.world.flush()
        return eid


def test_it_is_equipped_on_its_first_tick_and_starts_submerged() -> None:
    arena = Arena()
    assert arena.health.current == arena.health.max == TUNING.hp
    assert arena.world.get(arena.boss, Hurtbox).team == Team.NONE
    assert arena.world.get(arena.boss, Guard).active
    box = arena.world.get(arena.boss, Hitbox)
    assert (box.targets, box.active) == (Team.PLAYER, False)
    body = arena.world.get(arena.boss, Body)
    assert body.y + body.height / 2 == arena.state.home[1] + TUNING.depth
    assert arena.state.home == (18 * TILE + 16, WATER - 8)


def test_phases_are_thirds_of_its_health() -> None:
    assert [phase_for(hp, 18) for hp in (18, 13, 12, 7, 6, 1)] == [1, 1, 2, 2, 3, 3]


def test_the_phase_follows_its_health_and_never_goes_back() -> None:
    arena = Arena()
    arena.health.current = 12
    arena.tick()
    assert arena.state.phase == 2
    arena.health.current = 18
    arena.tick()
    assert arena.state.phase == 2
    arena.health.current = 5
    arena.tick()
    assert arena.state.phase == 3
    assert [event.phase for event in arena.phases] == [2, 3]


def test_it_sleeps_while_the_player_is_outside_its_arena() -> None:
    arena = Arena()
    arena.state.arena = (0.0, 0.0, 100.0, 100.0)
    arena.health.current = 5
    arena.tick()
    assert not arena.state.awake
    assert arena.state.phase == 1


def test_every_mode_sets_the_hurt_box_hit_box_and_armor() -> None:
    arena = Arena()
    boss = arena.boss
    expected = {
        "swim": (Team.NONE, False, True, True),
        "surface": (Team.ENEMY, True, True, True),
        "breach": (Team.ENEMY, True, True, False),
        "stunned": (Team.ENEMY, False, False, False),
        "dazed": (Team.ENEMY, False, True, True),
    }
    for mode, (team, contact, armor, top) in expected.items():
        arena.state.mode = mode
        arena.tick()
        assert arena.world.get(boss, Hurtbox).team == team, mode
        assert arena.world.get(boss, Hitbox).active == contact, mode
        guard = arena.world.get(boss, Guard)
        assert (guard.active, guard.top) == (armor, top), mode
    assert set(expected) <= set(MODES)


def test_it_aims_at_the_brightest_light_flare_over_lamp_over_lantern() -> None:
    arena = Arena()
    arena.world.get(arena.player, Body).x = 5 * TILE
    ctx = arena.ctx()
    player = arena.world.get(arena.player, Body)
    assert brightest(ctx) == (player.center_x, player.y + player.height / 2)
    arena.lamp(300)
    assert brightest(ctx) == (300, WATER - 64)
    arena.flare(500, WATER - 100)
    assert brightest(ctx) == (500, WATER - 100)


def test_a_fading_flare_loses_to_a_lamp_and_an_unlit_lamp_is_no_bait() -> None:
    arena = Arena()
    arena.lamp(200, lit=False)
    arena.lamp(400)
    arena.flare(500, WATER - 100, strength=0.5)
    assert brightest(arena.ctx()) == (400, WATER - 64)


def test_equals_go_to_the_nearest() -> None:
    arena = Arena()
    arena.lamp(100)
    arena.lamp(330)
    arena.lamp(600)
    assert brightest(arena.ctx()) == (330, WATER - 64)


def test_bait_outside_the_arena_is_ignored() -> None:
    arena = Arena()
    arena.state.arena = (0.0, 0.0, 320.0, 352.0)
    arena.lamp(500)
    ctx = arena.ctx()
    player = arena.world.get(arena.player, Body)
    assert brightest(ctx) == (player.center_x, player.y + player.height / 2)
