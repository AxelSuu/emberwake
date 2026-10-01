from __future__ import annotations

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, Source, make_room

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import World
from emberwake.engine.physics import Body
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import RoomEntered, RoomGraph, RoomStreamer, WorldGrid
from emberwake.game.player.controller import Motor
from emberwake.game.rooms import RoomTuning, room_system
from emberwake.game.scenes.gameplay import COLLISIONS

BOX = "\n".join(["#" * 20, *["#" + "." * 18 + "#"] * 9, "#" * 20])
DEFS = from_data(Defs, {"level_fields": {"Generated": {"type": "Bool"}}})


def setup(**cells: tuple[int, int]) -> tuple[World, list[RoomEntered], RoomStreamer]:
    rooms = [make_room(name, cell, BOX) for name, cell in cells.items()]
    graph = RoomGraph(from_data(Project, build_project(Source(DEFS, rooms))).levels)
    streamer = RoomStreamer(graph, WorldGrid(), "Collisions", COLLISIONS)
    world, bus, entered = World(), EventBus(), []
    bus.subscribe(RoomEntered, entered.append)
    for resource in (streamer, bus, RoomTuning()):
        world.insert_resource(resource)
    return world, entered, streamer


def player(world: World, x: float, y: float, vy: float = 0.0) -> Motor:
    motor = Motor(vy=vy)
    world.spawn(Body(x, y, 10, 20), motor)
    world.flush()
    return motor


def test_entering_a_room_streams_and_publishes():
    world, entered, streamer = setup(Left=(0, 0), Right=(1, 0), Far=(2, 0))
    streamer.enter("Left")
    player(world, 330, 100)
    room_system(world, 1 / 60)
    assert entered == [RoomEntered("Right", "Left", 335, 120)]
    assert streamer.active == "Right"
    assert set(streamer.loaded) == {"Left", "Right", "Far"}
    room_system(world, 1 / 60)
    assert len(entered) == 1


def test_entering_through_the_floor_boosts_upward():
    world, entered, streamer = setup(Up=(0, 0), Down=(0, 1))
    streamer.enter("Down")
    motor = player(world, 100, 160, vy=-50)
    room_system(world, 1 / 60)
    assert entered[0].room == "Up"
    assert motor.vy == -RoomTuning().entry_boost


def test_entering_from_above_keeps_velocity():
    world, _, streamer = setup(Up=(0, 0), Down=(0, 1))
    streamer.enter("Up")
    motor = player(world, 100, 170, vy=200)
    room_system(world, 1 / 60)
    assert (streamer.active, motor.vy) == ("Down", 200)
