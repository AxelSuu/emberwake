"""Scenario tests for docs/specs/player-movement.md, driven by per-tick action frames."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from emberwake.engine.input import InputState
from emberwake.engine.physics import Tile, TileGrid
from emberwake.game.actions import Action
from emberwake.game.player.controller import (
    Dashed,
    Died,
    Jumped,
    Landed,
    PlayerEvent,
    PlayerState,
    new_player,
    step,
)
from emberwake.game.player.tuning import PlayerTuning

if TYPE_CHECKING:
    from collections.abc import Callable


TS = 16
DT = 1 / 60
TUNING = PlayerTuning()
L, R, U, D, JUMP, DASH = Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN, Action.JUMP, Action.DASH

FLAT = [
    "#..........................................#",
    "#..........................................#",
    "#..........................................#",
    "#..........................................#",
    "#..........................................#",
    "#..........................................#",
    "#..P.......................................#",
    "############################################",
]


class Sim:
    def __init__(self, rows: list[str], tuning: PlayerTuning = TUNING) -> None:
        self.grid = TileGrid.from_rows(rows, {"#": Tile.SOLID, "=": Tile.ONE_WAY, "^": Tile.HAZARD})
        (row, column), *_ = [
            (r, c) for r, line in enumerate(rows) for c, ch in enumerate(line) if ch == "P"
        ]
        self.tuning = tuning
        self.body, self.motor = new_player(column * TS + TS / 2, (row + 1) * TS, tuning)
        self.actions = InputState[Action]()
        self.tick = 0
        self.events: list[tuple[int, PlayerEvent]] = []

    def frame(self, *actions: Action) -> list[PlayerEvent]:
        self.actions.advance(frozenset(actions))
        self.tick += 1
        events = step(self.body, self.motor, self.actions, self.grid, self.tuning, DT)
        self.events += [(self.tick, event) for event in events]
        return events

    def hold(self, ticks: int, *actions: Action) -> None:
        for _ in range(ticks):
            self.frame(*actions)

    def until(
        self, done: Callable[[Sim], bool], policy: Callable[[Sim], set[Action]], limit: int = 600
    ) -> None:
        for _ in range(limit):
            if done(self):
                return
            self.frame(*policy(self))
        pytest.fail("scenario did not finish")

    def of(self, kind: type) -> list[tuple[int, PlayerEvent]]:
        return [(tick, event) for tick, event in self.events if isinstance(event, kind)]


def settled(rows: list[str] = FLAT) -> Sim:
    sim = Sim(rows)
    sim.hold(2)
    assert sim.motor.grounded
    sim.events.clear()
    return sim


def jump_height(hold_ticks: int) -> float:
    sim = settled()
    start = lowest = sim.body.y
    for tick in range(240):
        sim.frame(*([JUMP] if tick < hold_ticks else []))
        lowest = min(lowest, sim.body.y)
        if sim.motor.grounded and tick > 2:
            break
    return start - lowest


def test_run_reaches_max_speed_within_6_ticks_and_caps():
    sim = settled()
    speeds = []
    for _ in range(40):
        sim.frame(R)
        speeds.append(sim.motor.vx)
    assert speeds[5] == pytest.approx(TUNING.max_run)
    assert max(speeds) <= TUNING.max_run


def test_full_jump_height_between_3_5_and_4_5_tiles():
    assert 3.5 * TS <= jump_height(60) <= 4.5 * TS


def test_tap_jump_is_below_2_tiles():
    assert jump_height(1) < 2 * TS


def test_running_jump_clears_6_tile_gap():
    edge = 10
    rows = [
        "#..............................#",
        "#..............................#",
        "#..............................#",
        "#..............................#",
        "#..............................#",
        "#..P...........................#",
        "###########......###############",
        "###########^^^^^^###############",
    ]
    assert rows[6].index(".") == edge + 1
    sim = settled(rows)
    edge_x = (edge + 1) * TS
    sim.until(
        lambda s: (s.body.x > 18 * TS and s.motor.grounded) or s.motor.dead,
        lambda s: {R, JUMP} if s.body.x + s.body.width >= edge_x - 2 else {R},
    )
    assert not sim.motor.dead


def walk_off_ledge_ticks() -> int:
    sim = settled(LEDGE)
    settle = sim.tick
    sim.until(lambda s: not s.motor.grounded, lambda s: {R})
    return sim.tick - settle


LEDGE = [
    "#..............#",
    "#..............#",
    "#..............#",
    "#..P...........#",
    "#######........#",
    "#..............#",
    "#..............#",
    "#..............#",
    "################",
]


@pytest.mark.parametrize(
    ("late", "jumps"), [(1, True), (TUNING.coyote, True), (TUNING.coyote + 1, False)]
)
def test_coyote_time(late: int, jumps: bool):
    airborne_at = walk_off_ledge_ticks()
    sim = settled(LEDGE)
    sim.hold(airborne_at + late - 1, R)
    assert not sim.motor.grounded
    jumped = any(isinstance(e, Jumped) for e in sim.frame(R, JUMP))
    assert jumped is jumps


FALL = [
    "#........#",
    "#...P....#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "##########",
]


def landing_tick() -> int:
    sim = Sim(FALL)
    sim.until(lambda s: bool(s.of(Landed)), lambda s: set())
    return sim.of(Landed)[0][0]


@pytest.mark.parametrize(
    ("early", "jumps"), [(0, True), (TUNING.jump_buffer - 1, True), (TUNING.jump_buffer, False)]
)
def test_jump_buffer(early: int, jumps: bool):
    first_grounded_tick = landing_tick() + 1
    sim = Sim(FALL)
    press_at = first_grounded_tick - early
    sim.hold(press_at - 1)
    sim.frame(JUMP)
    sim.hold(early)
    assert bool(sim.of(Jumped)) is jumps


CEILING = [
    "#..........#",
    "#..........#",
    "#..........#",
    "#####......#",
    "#..........#",
    "#.....P....#",
    "############",
]


@pytest.mark.parametrize(
    ("overlap", "passes"),
    [(1, True), (TUNING.corner_correction, True), (TUNING.corner_correction + 2, False)],
)
def test_corner_correction(overlap: int, passes: bool):
    sim = settled(CEILING)
    sim.body.x = 5 * TS - overlap
    highest = sim.body.y
    for _ in range(30):
        sim.frame(JUMP)
        highest = min(highest, sim.body.y)
    assert (highest < 3 * TS) is passes


WALL = [
    "#........#",
    "#.......P#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "##########",
]


def test_wall_slide_slows_to_cap_and_stays_below_it():
    sim = Sim(WALL)
    sim.until(lambda s: s.motor.state is PlayerState.WALL_SLIDE, lambda s: {R})
    sim.until(lambda s: s.motor.vy <= TUNING.wall_slide_max, lambda s: {R}, limit=10)
    for _ in range(30):
        sim.frame(R)
        assert sim.motor.state is PlayerState.WALL_SLIDE
        assert sim.motor.vy <= TUNING.wall_slide_max
    assert sim.motor.vy == pytest.approx(TUNING.wall_slide_max)


def test_wall_jump_moves_away_and_up():
    sim = Sim(WALL)
    sim.hold(10, R)
    y_before = sim.body.y
    events = sim.frame(R, JUMP)
    assert [e.wall for e in events if isinstance(e, Jumped)] == [1]
    sim.hold(8, R, JUMP)
    assert sim.motor.vx < 0
    assert sim.body.y < y_before


def test_horizontal_dash_distance():
    sim = settled()
    x0 = sim.body.x
    sim.frame(DASH)
    sim.until(lambda s: s.motor.dash_ticks == 0, lambda s: set())
    assert 4 * TS <= sim.body.x - x0 <= 5 * TS


def test_dash_charge_refills_only_after_landing():
    sim = Sim(FALL)
    sim.frame(DASH)
    sim.hold(TUNING.dash_ticks + 1)
    sim.frame(DASH)
    assert len(sim.of(Dashed)) == 1
    sim.until(lambda s: s.motor.grounded, lambda s: set())
    sim.hold(1)
    sim.frame(DASH)
    assert len(sim.of(Dashed)) == 2


def test_dash_without_direction_uses_facing():
    sim = settled()
    sim.hold(3, L)
    sim.hold(2)
    (event,) = sim.frame(DASH)
    assert isinstance(event, Dashed)
    assert (event.dx, event.dy) == (-1, 0)


ONE_WAY = [
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#..====..#",
    "#........#",
    "#....P...#",
    "##########",
]


def test_jump_up_through_one_way_and_land_on_it():
    sim = settled(ONE_WAY)
    sim.hold(40, JUMP)
    sim.until(lambda s: s.motor.grounded, lambda s: set())
    assert sim.body.bottom == 5 * TS
    assert sim.motor.on_one_way


def test_down_jump_drops_through_one_way():
    sim = settled(ONE_WAY)
    sim.hold(40, JUMP)
    sim.until(lambda s: s.motor.grounded, lambda s: set())
    sim.hold(2)
    sim.frame(D, JUMP)
    sim.until(lambda s: s.motor.grounded, lambda s: {D})
    assert sim.body.bottom == 8 * TS
    assert not sim.of(Jumped)[1:]


def test_hazard_kills():
    rows = ["#.......#", "#.P..^..#", "#########"]
    sim = settled(rows)
    sim.until(lambda s: s.motor.dead, lambda s: {R}, limit=120)
    assert sim.of(Died)


def test_falling_out_of_the_room_kills():
    rows = ["#.......#", "#........", "#.P......", "#####...."]
    sim = settled(rows)
    sim.until(lambda s: s.motor.dead, lambda s: {R}, limit=240)
    assert sim.of(Died)


def test_deterministic():
    def run() -> tuple[float, float, float, float]:
        sim = settled()
        for tick in range(200):
            sim.frame(*([R] if tick % 7 else [R, JUMP]), *([DASH] if tick == 50 else []))
        return sim.body.x, sim.body.y, sim.motor.vx, sim.motor.vy

    assert run() == run()


def test_tuning_is_respected():
    slow = replace(TUNING, max_run=60)
    sim = Sim(FLAT, slow)
    sim.hold(2)
    sim.hold(30, R)
    assert sim.motor.vx == pytest.approx(60)


def test_no_dash_without_the_ability():
    sim = settled()
    sim.actions.advance(frozenset({DASH}))
    events = step(sim.body, sim.motor, sim.actions, sim.grid, sim.tuning, DT, can_dash=False)
    assert not [event for event in events if isinstance(event, Dashed)]
