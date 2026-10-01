from __future__ import annotations

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import COMPONENTS, Schedule, World
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, Tile, TileGrid, TileSource
from emberwake.game.actions import Action
from emberwake.game.player.controller import Landed, Motor, new_player
from emberwake.game.player.system import player_system
from emberwake.game.player.tuning import PlayerTuning

ROWS = ["#....#", "#....#", "#....#", "######"]


def schedule() -> Schedule:
    only = Schedule(["physics"])
    only.add("physics", player_system)
    return only


def world_with_players(*feet: tuple[float, float]) -> tuple[World, list[Landed]]:
    world = World()
    bus = EventBus()
    landed: list[Landed] = []
    bus.subscribe(Landed, landed.append)
    world.insert_resource(InputState[Action]())
    world.insert_resource(TileGrid.from_rows(ROWS, {"#": Tile.SOLID}), key=TileSource)
    world.insert_resource(PlayerTuning())
    world.insert_resource(bus)
    for foot in feet:
        world.spawn(*new_player(*foot, PlayerTuning()))
    return world, landed


def test_steps_every_living_player_and_publishes_events():
    world, landed = world_with_players((24, 16), (72, 16))
    tick = schedule()
    for _ in range(30):
        tick.run(world, 1 / 60)
    assert len(landed) == 2
    assert all(motor.grounded for _, motor in world.query(Motor))


def test_skips_dead_players():
    world, _ = world_with_players((24, 16))
    world.flush()
    (eid, body, motor), *_ = world.query(Body, Motor)
    motor.dead = True
    y = body.y
    schedule().run(world, 1 / 60)
    assert world.get(eid, Body).y == y


def test_player_components_are_registered():
    assert COMPONENTS["Body"] is Body
    assert COMPONENTS["Motor"] is Motor
