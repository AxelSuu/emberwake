from __future__ import annotations

import pytest
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, Source, make_room

from emberwake.engine.core.serde import from_data
from emberwake.engine.physics import Tile
from emberwake.engine.world.ldtk import Level, Project
from emberwake.engine.world.rooms import Room, RoomGraph, RoomStreamer, WorldGrid

LEGEND = {1: Tile.SOLID, 2: Tile.ONE_WAY, 3: Tile.HAZARD}
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
BOX = "\n".join([WALL, *[INSIDE] * 9, WALL])
DEFS = from_data(Defs, {"level_fields": {"Generated": {"type": "Bool"}}})
CELL = (320, 176)


def levels(**cells: tuple[int, int]) -> list[Level]:
    rooms = [make_room(name, cell, BOX) for name, cell in cells.items()]
    return from_data(Project, build_project(Source(DEFS, rooms))).levels


# A B C .
# D . . .
# . . . E
GRAPH = RoomGraph(levels(A=(0, 0), B=(1, 0), C=(2, 0), D=(0, 1), E=(3, 2)))


def test_adjacency_from_shared_edges():
    assert GRAPH.neighbours("A") == ["B", "D"]
    assert GRAPH.neighbours("C") == ["B"]
    assert GRAPH.neighbours("E") == []
    assert GRAPH.within("A", 1) == {"A", "B", "D"}
    assert GRAPH.within("A", 2) == {"A", "B", "C", "D"}


def test_corners_are_not_neighbours():
    graph = RoomGraph(levels(A=(0, 0), B=(1, 1)))
    assert graph.neighbours("A") == []


def test_room_at():
    assert GRAPH.room_at(10, 10) == "A"
    assert GRAPH.room_at(CELL[0], 0) == "B"
    assert GRAPH.room_at(CELL[0] - 0.5, CELL[1] - 0.5) == "A"
    assert GRAPH.room_at(CELL[0] * 1.5, CELL[1] * 1.5) is None


def room(name: str) -> Room:
    level = GRAPH.levels[name]
    return Room(level, level.layer("Collisions").to_tile_grid(LEGEND))


def test_world_grid_routes_cells_to_rooms():
    grid = WorldGrid()
    grid.add(room("A"))
    grid.add(room("B"))
    assert grid.get(0, 0) is Tile.SOLID
    assert grid.get(1, 1) is Tile.EMPTY
    assert grid.get(20, 0) is Tile.SOLID
    assert grid.get(21, 1) is Tile.EMPTY
    assert grid.get(40, 1) is Tile.EMPTY
    assert grid.get(-1, 0) is Tile.EMPTY
    b = grid.rooms[1]
    grid.remove(b)
    assert grid.get(20, 0) is Tile.EMPTY


def test_world_grid_set_changes_the_owning_room():
    grid = WorldGrid()
    grid.add(room("B"))
    assert grid.set(21, 1, Tile.SOLID)
    assert grid.get(21, 1) is Tile.SOLID
    assert grid.rooms[0].grid.get(1, 1) is Tile.SOLID
    assert not grid.set(1, 1, Tile.SOLID)


def test_world_grid_counts_changes_to_its_tiles():
    grid = WorldGrid()
    b = room("B")
    grid.add(b)
    added = grid.version
    grid.set(21, 1, Tile.SOLID)
    grid.set(21, 1, Tile.SOLID)
    assert grid.version == added + 1
    grid.remove(b)
    assert grid.version == added + 2


def test_world_grid_rejects_misaligned_rooms():
    level = GRAPH.levels["A"]
    shifted = Level(level.identifier, level.iid, 8, 0, level.width, level.height)
    with pytest.raises(ValueError, match="aligned"):
        WorldGrid().add(Room(shifted, room("A").grid))


def test_void_is_below_every_room_spanning_x():
    grid = WorldGrid()
    grid.add(room("A"))
    grid.add(room("D"))
    assert not grid.void(10, CELL[1] + 10)
    assert grid.void(10, 2 * CELL[1] + 1)
    assert not grid.void(10, -500)
    assert grid.void(CELL[0] + 10, 0)


def test_streamer_loads_neighbours_and_unloads_rooms_two_steps_away():
    events: list[tuple[str, str, bool]] = []
    grid = WorldGrid()

    def on_unload(r: Room) -> None:
        events.append(("unload", r.name, r in grid.rooms))

    streamer = RoomStreamer(
        GRAPH,
        grid,
        "Collisions",
        LEGEND,
        on_load=lambda r: events.append(("load", r.name, r in grid.rooms)),
        on_unload=on_unload,
    )
    streamer.enter("A")
    assert set(streamer.loaded) == {"A", "B", "D"}
    assert events == [("load", "A", True), ("load", "B", True), ("load", "D", True)]
    events.clear()
    streamer.enter("B")
    assert streamer.active == "B"
    assert set(streamer.loaded) == {"A", "B", "C"}
    assert events == [("unload", "D", True), ("load", "C", True)]
    assert {r.name for r in grid.rooms} == {"A", "B", "C"}


def test_streamer_reload_swaps_the_graph():
    streamer = RoomStreamer(GRAPH, WorldGrid(), "Collisions", LEGEND)
    streamer.enter("C")
    old = streamer.loaded["C"]
    streamer.reload(RoomGraph(levels(A=(0, 0), B=(1, 0), C=(2, 0))))
    assert set(streamer.loaded) == {"B", "C"}
    assert streamer.loaded["C"] is not old
