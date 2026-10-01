"""The lantern swing: phases, directions, enemy hits, pogo, recoil and Struck events."""

from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, Tile, TileGrid, TileSource
from emberwake.engine.world.rooms import WorldGrid
from emberwake.game.actions import Action
from emberwake.game.combat import Health, Hitbox, Hurtbox, Killed, Knockback, Team, combat_system
from emberwake.game.enemies import Brain, EnemyTuning, enemy_system
from emberwake.game.light import LightTuning
from emberwake.game.player.controller import Motor
from emberwake.game.player.swing import (
    Direction,
    Strikeable,
    Struck,
    Swing,
    SwingHit,
    SwingTuning,
    strike_system,
    swing_system,
)
from emberwake.game.player.tuning import PlayerTuning

STEP = 1 / 60
FLOOR = 9
TUNING = SwingTuning()


class Room:
    """A 30x10 tile room with a floor, a player standing at `x` and what the test adds."""

    def __init__(self, x: float = 100, *, grounded: bool = True, walls: tuple[int, ...] = ()):
        self.world = World()
        grid = TileGrid(30, 10, 16, bytearray(300))
        for column in range(30):
            grid.set(column, FLOOR, Tile.SOLID)
        for column in walls:
            for row in range(FLOOR):
                grid.set(column, row, Tile.SOLID)
        self.grid = grid
        self.actions = InputState[Action]()
        self.bus = EventBus()
        self.struck: list[Struck] = []
        self.hits: list[SwingHit] = []
        self.killed: list[Killed] = []
        self.bus.subscribe(Struck, self.struck.append)
        self.bus.subscribe(SwingHit, self.hits.append)
        self.bus.subscribe(Killed, self.killed.append)
        for resource in (self.actions, self.bus, TUNING, PlayerTuning(), EnemyTuning()):
            self.world.insert_resource(resource)
        self.world.insert_resource(LightTuning())
        self.world.insert_resource(grid, key=TileSource)
        self.world.insert_resource(grid, key=WorldGrid)
        y = FLOOR * 16 - 20 if grounded else 40
        self.player = self.world.spawn(
            Body(x, y, 10, 20), Motor(grounded=grounded), Swing(), Hitbox(targets=Team.ENEMY)
        )
        self.world.flush()

    @property
    def motor(self) -> Motor:
        return self.world.get(self.player, Motor)

    @property
    def swing(self) -> Swing:
        return self.world.get(self.player, Swing)

    @property
    def hitbox(self) -> Hitbox:
        return self.world.get(self.player, Hitbox)

    def enemy(self, x: float, y: float = FLOOR * 16 - 16, hp: int = 2) -> EntityId:
        eid = self.world.spawn(
            Body(x, y, 16, 16),
            Health(hp, iframes=0.0),
            Hurtbox(Team.ENEMY),
            Brain("clockrat", state="patrol"),
            Hitbox(targets=Team.PLAYER, size=(16, 16), active=True),
        )
        self.world.flush()
        return eid

    def thing(self, x: float, y: float, *, bouncy: bool = False) -> EntityId:
        eid = self.world.spawn(Body(x, y, 16, 16), Strikeable(bouncy=bouncy))
        self.world.flush()
        return eid

    def tick(self, *held: Action, ticks: int = 1) -> None:
        for _ in range(ticks):
            self.actions.advance(frozenset(held))
            swing_system(self.world, STEP)
            self.world.flush()
            combat_system(self.world, STEP)
            strike_system(self.world, STEP)
            self.world.flush()

    def swing_now(self, *held: Action) -> None:
        """Press swing and run until the hitbox is active."""
        self.tick(Action.SWING, *held)
        self.tick(*held, ticks=TUNING.windup)


def test_a_swing_runs_windup_active_recovery_then_ends() -> None:
    room = Room()
    room.tick(Action.SWING)
    assert room.swing.tick == 1
    assert not room.hitbox.active
    room.tick(ticks=TUNING.windup)
    assert room.hitbox.active
    room.tick(ticks=TUNING.active)
    assert not room.hitbox.active
    room.tick(ticks=TUNING.recovery)
    assert room.swing.tick == 0


def test_a_buffered_press_starts_the_next_swing_right_away() -> None:
    room = Room()
    room.tick(Action.SWING)
    room.tick(ticks=TUNING.length - 3)
    room.tick(Action.SWING)
    room.tick(ticks=3)
    assert room.swing.tick in {1, 2}


def test_direction_comes_from_the_held_keys() -> None:
    room = Room()
    room.tick(Action.SWING, Action.UP)
    assert room.swing.direction is Direction.UP
    grounded_down = Room()
    grounded_down.tick(Action.SWING, Action.DOWN)
    assert grounded_down.swing.direction is Direction.FORWARD
    air = Room(grounded=False)
    air.tick(Action.SWING, Action.DOWN)
    assert air.swing.direction is Direction.DOWN


def test_two_swings_kill_a_clockrat_and_knock_it_away() -> None:
    room = Room(x=100)
    rat = room.enemy(115)
    room.swing_now()
    assert room.world.get(rat, Health).current == 1
    assert room.world.has(rat, Knockback)
    assert room.world.get(rat, Knockback).vx > 0
    assert room.hits[0].enemy
    room.tick(ticks=TUNING.length)
    room.world.get(room.player, Body).x = room.world.get(rat, Body).x - 15
    room.swing_now()
    assert room.killed[0].target == rat


def test_one_swing_hits_an_enemy_once() -> None:
    room = Room()
    rat = room.enemy(115, hp=5)
    room.swing_now()
    room.tick(ticks=TUNING.active)
    assert room.world.get(rat, Health).current == 4


def test_a_forward_hit_recoils_the_player() -> None:
    room = Room()
    room.enemy(115)
    room.swing_now()
    assert room.motor.vx == -TUNING.recoil


def test_swinging_into_a_wall_recoils_and_sparks() -> None:
    room = Room(x=100, walls=(7,))
    room.swing_now()
    assert room.motor.vx == -TUNING.recoil
    assert room.hits
    assert not room.hits[0].enemy


def test_a_down_swing_on_an_enemy_bounces_and_refills_the_dash() -> None:
    room = Room(grounded=False)
    room.enemy(97, y=60)
    room.motor.dash_charges = 0
    room.swing_now(Action.DOWN)
    assert room.motor.vy == -TUNING.pogo_speed
    assert room.motor.dash_charges == PlayerTuning().dash_charges


def test_a_down_swing_bounces_off_spikes() -> None:
    room = Room(grounded=False)
    room.grid.set(6, 4, Tile.HAZARD)
    room.swing_now(Action.DOWN)
    assert room.motor.vy == -TUNING.pogo_speed
    assert room.swing.bounced


def test_up_and_down_swings_only_reach_up_and_down() -> None:
    room = Room()
    beside = room.enemy(115)
    room.swing_now(Action.UP)
    assert room.world.get(beside, Health).current == 2
    room.tick(ticks=TUNING.length)
    above = room.enemy(97, y=FLOOR * 16 - 20 - 18)
    room.swing_now(Action.UP)
    assert room.world.get(above, Health).current == 1


def test_strikeables_get_one_struck_per_swing_and_bouncy_ones_pogo() -> None:
    room = Room(grounded=False)
    lamp = room.thing(97, 58, bouncy=True)
    room.swing_now(Action.DOWN)
    room.tick(ticks=TUNING.active)
    assert [event.target for event in room.struck] == [lamp]
    assert room.struck[0].direction is Direction.DOWN
    assert room.swing.bounced


def test_a_strikeable_remembers_how_it_was_struck_for_that_tick_only() -> None:
    room = Room()
    crate = room.thing(115, FLOOR * 16 - 16)
    room.swing_now()
    assert room.world.get(crate, Strikeable).struck is Direction.FORWARD
    room.tick()
    assert room.world.get(crate, Strikeable).struck is None


def test_a_dash_cancels_the_swing() -> None:
    room = Room()
    room.swing_now()
    room.motor.dash_ticks = 3
    room.tick()
    assert room.swing.tick == 0
    assert not room.hitbox.active


def test_a_knocked_enemy_staggers_without_hurting_then_recovers() -> None:
    room = Room()
    rat = room.enemy(115)
    room.swing_now()
    enemy_system(room.world, STEP)
    room.world.flush()
    brain = room.world.get(rat, Brain)
    assert brain.stagger > 0
    assert not room.world.get(rat, Hitbox).active
    for _ in range(round(TUNING.stagger * 60) + 2):
        enemy_system(room.world, STEP)
        room.world.flush()
    assert brain.stagger <= 0
    assert room.world.get(rat, Hitbox).active
