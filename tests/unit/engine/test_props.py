from __future__ import annotations

import pytest

from emberwake.engine.physics import HAS_PYMUNK, Body, Tile, TileGrid
from emberwake.engine.physics.props import PropWorld, greedy_boxes

NO_PYMUNK = pytest.mark.skipif(not HAS_PYMUNK, reason="no pymunk")
BACKENDS = ["simple", pytest.param("pymunk", marks=NO_PYMUNK)]
STEP = 1 / 60
FLOOR_Y = 9 * 16


def room(walls: tuple[int, ...] = ()) -> TileGrid:
    grid = TileGrid(30, 10, 16, bytearray(300))
    for column in range(30):
        grid.set(column, 9, Tile.SOLID)
    for column in walls:
        for row in range(9):
            grid.set(column, row, Tile.SOLID)
    return grid


def world(backend: str, grid: TileGrid | None = None) -> PropWorld:
    return PropWorld(grid or room(), (0, 0, 30, 10), backend)


def run(props: PropWorld, seconds: float) -> None:
    for _ in range(round(seconds / STEP)):
        props.step(STEP)


def test_greedy_meshing_merges_a_floor_into_one_box() -> None:
    assert greedy_boxes(room(), (0, 0, 30, 10)) == [(0, 9, 30, 1)]


def test_greedy_meshing_merges_rows_into_blocks() -> None:
    grid = room()
    for row in range(5, 9):
        grid.set(3, row, Tile.SOLID)
        grid.set(4, row, Tile.SOLID)
    boxes = greedy_boxes(grid, (0, 0, 30, 10))
    assert (3, 5, 2, 4) in boxes
    assert (0, 9, 30, 1) in boxes
    assert len(boxes) == 2


def test_greedy_meshing_keeps_gaps_and_ignores_other_kinds() -> None:
    grid = room()
    grid.set(10, 9, Tile.EMPTY)
    grid.set(20, 8, Tile.ONE_WAY)
    boxes = greedy_boxes(grid, (0, 0, 30, 10))
    assert boxes == [(0, 9, 10, 1), (11, 9, 19, 1)]


def test_greedy_meshing_stays_inside_the_region() -> None:
    assert greedy_boxes(room(), (5, 9, 4, 1)) == [(5, 9, 4, 1)]
    assert greedy_boxes(room(), (5, 0, 4, 5)) == []


def test_unknown_backend_choice_and_missing_pymunk() -> None:
    assert world("simple").backend == "simple"
    assert world("auto").backend == ("pymunk" if HAS_PYMUNK else "simple")


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_box_falls_and_comes_to_rest_on_the_floor(backend: str) -> None:
    props = world(backend)
    box = props.add_box(100, 40, 12, 12)
    run(props, 3.0)
    state = props.state(box)
    assert state.y == pytest.approx(FLOOR_Y - 6, abs=2.5)
    assert abs(state.vy) < 5


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_circle_bounces(backend: str) -> None:
    props = world(backend)
    ball = props.add_circle(100, 40, 5, bounce=0.8)
    lowest, rebound = 0.0, 0.0
    for _ in range(200):
        props.step(STEP)
        state = props.state(ball)
        lowest = max(lowest, state.y)
        if lowest > FLOOR_Y - 8 and state.vy < -50:
            rebound = max(rebound, -state.vy)
    assert rebound > 50


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_thrown_prop_travels_and_stops_at_a_wall(backend: str) -> None:
    props = world(backend, room(walls=(12,)))
    ball = props.add_circle(100, 140, 4)
    props.push(ball, 200, -50)
    run(props, 2.0)
    assert props.state(ball).x < 12 * 16


@pytest.mark.parametrize("backend", BACKENDS)
def test_removed_props_are_gone(backend: str) -> None:
    props = world(backend)
    box = props.add_box(100, 40, 8, 8)
    props.remove(box)
    props.remove(box)
    with pytest.raises(KeyError):
        props.state(box)


@pytest.mark.parametrize("backend", BACKENDS)
def test_refresh_follows_changed_tiles(backend: str) -> None:
    grid = room()
    props = world(backend, grid)
    box = props.add_box(100, 40, 12, 12)
    run(props, 2.0)
    for column in range(30):
        grid.set(column, 9, Tile.EMPTY)
    props.refresh()
    run(props, 1.0)
    assert props.state(box).y > FLOOR_Y + 20


@NO_PYMUNK
def test_the_player_pushes_a_box_in_pymunk() -> None:
    props = world("pymunk")
    box = props.add_box(120, FLOOR_Y - 8, 14, 14, mass=0.5)
    run(props, 0.5)
    player = Body(90, FLOOR_Y - 20, 10, 20)
    for _ in range(90):
        player.x += 60 * STEP
        props.set_player(player, 60, 0)
        props.step(STEP)
    assert props.state(box).x > 125


@NO_PYMUNK
def test_pymunk_boxes_tumble_when_pushed_off_a_ledge() -> None:
    grid = room()
    for column in range(10, 30):
        grid.set(column, 9, Tile.EMPTY)
        grid.set(column, 7, Tile.EMPTY)
    for column in range(10):
        grid.set(column, 7, Tile.SOLID)
    props = world("pymunk", grid)
    box = props.add_box(150, 90, 12, 12)
    props.push(box, 0, 0)
    props.push(box, 60, 0)
    run(props, 1.5)
    assert abs(props.state(box).angle) > 5


def test_simple_backend_ignores_the_player() -> None:
    props = world("simple")
    box = props.add_box(120, FLOOR_Y - 8, 14, 14)
    run(props, 0.5)
    x = props.state(box).x
    props.set_player(Body(110, FLOOR_Y - 20, 10, 20), 100, 0)
    run(props, 0.5)
    assert props.state(box).x == pytest.approx(x, abs=0.5)
