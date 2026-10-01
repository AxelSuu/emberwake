from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from emberwake.engine.physics import Body, Tile, TileGrid, move, overlaps

LEGEND = {"#": Tile.SOLID, "=": Tile.ONE_WAY, "^": Tile.HAZARD}
TS = 16


def grid(*rows: str) -> TileGrid:
    return TileGrid.from_rows(rows, LEGEND, TS)


ROOM = grid(
    "##########",
    "#........#",
    "#........#",
    "#...==...#",
    "#........#",
    "#.....^..#",
    "##########",
)


def test_from_rows_and_get():
    g = grid("#.", ".=")
    assert (g.get(0, 0), g.get(1, 0), g.get(1, 1)) == (Tile.SOLID, Tile.EMPTY, Tile.ONE_WAY)
    assert g.get(-1, 0) is Tile.EMPTY
    assert g.pixel_size == (32, 32)


def test_rejects_ragged_rows_and_wrong_cell_count():
    with pytest.raises(ValueError, match="equal length"):
        grid("##", "#")
    with pytest.raises(ValueError, match="expected 4 cells"):
        TileGrid(2, 2, TS, bytearray(3))


def test_falls_and_lands_on_floor():
    body = Body(32, 32, 10, 20)
    contacts = move(ROOM, body, 0, 200)
    assert contacts.ground
    assert body.bottom == 6 * TS


def test_runs_into_walls():
    body = Body(32, 70, 10, 20)
    assert move(ROOM, body, 500, 0).right
    assert body.x + body.width == 9 * TS
    assert move(ROOM, body, -500, 0).left
    assert body.x == TS


def test_hits_ceiling():
    body = Body(32, 40, 10, 20)
    assert move(ROOM, body, 0, -100).ceiling
    assert body.y == TS


def test_one_way_blocks_from_above_only():
    above = Body(4 * TS + 2, 3 * TS - 20, 10, 20)
    contacts = move(ROOM, above, 0, 5)
    assert contacts.ground
    assert contacts.one_way
    assert above.bottom == 3 * TS

    below = Body(4 * TS + 2, 4 * TS + 2, 10, 20)
    assert not move(ROOM, below, 0, -40).ceiling


def test_drop_through_one_way():
    body = Body(4 * TS + 2, 3 * TS - 20, 10, 20)
    assert not move(ROOM, body, 0, 5, drop_through=True).ground
    assert body.bottom == 3 * TS + 5


def test_no_tunnelling_through_thin_wall():
    thin = grid("#....#....#")
    body = Body(TS, 0, 10, 10)
    assert move(thin, body, 2 * TS * 10, 0).right
    assert body.x + body.width == 5 * TS


def test_overlaps_kinds():
    assert overlaps(ROOM, 6 * TS + 4, 5 * TS + 4, 4, 4, kinds={Tile.HAZARD})
    assert not overlaps(ROOM, 6 * TS + 4, 5 * TS + 4, 4, 4)
    assert overlaps(ROOM, 0, 0, 1, 1)


def test_touching_is_not_overlapping():
    assert not overlaps(ROOM, TS, TS, TS, TS)


@given(
    st.lists(st.tuples(st.floats(-60, 60), st.floats(-60, 60)), max_size=30),
    st.floats(TS, 8 * TS - 10),
    st.floats(TS, 5 * TS - 20),
)
def test_moves_never_end_inside_solids(moves: list[tuple[float, float]], x: float, y: float):
    body = Body(x, y, 10, 20)
    if overlaps(ROOM, body.x, body.y, body.width, body.height):
        return
    for dx, dy in moves:
        move(ROOM, body, dx, dy)
        assert not overlaps(ROOM, body.x, body.y, body.width, body.height)
