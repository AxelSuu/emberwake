"""Pilot bots through the Quarter's first rooms: Wake, Well Climb, Old Guild and Lamp Row."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tests.integration.test_greybox import Leg, at, climb, in_room, run, walk

from emberwake.engine.physics import Body
from emberwake.engine.world.rooms import RoomEntered
from emberwake.game.beacons import BeaconLit
from emberwake.game.breakables import Broken
from emberwake.game.enemies import Brain
from emberwake.game.grants import Granted
from emberwake.game.interact import Collected
from emberwake.game.lamps import Lamp, LampLit
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.game.context import GameContext

WAKE = (0, 11)
WELL = (1, 8)
GUILD = (2, 9)
ROW = (2, 8)
WELL_TOP = at(WELL, 0, 6)[1]
LEDGE = at(WELL, 0, 21)[1]


def x(cell: tuple[int, int], col: float) -> float:
    return at(cell, col + 0.5)[0]


def wake() -> list:
    return [
        walk(
            Leg(x(WAKE, 8)),
            Leg(x(WAKE, 8), interact=True),
            Leg(x(WAKE, 17)),
            Leg(x(WAKE, 22), jump=True),
            Leg(x(WAKE, 29)),
        ),
        climb(WELL_TOP, 1, in_room("Lamp_Row")),
    ]


ROW_TO_GAP = [
    Leg(x(ROW, 8)),
    Leg(x(ROW, 8), swing=True),
    Leg(x(ROW, 12)),
    Leg(x(ROW, 16), jump=True),
    Leg(x(ROW, 26)),
    Leg(x(ROW, 30), jump=True),
    Leg(x(ROW, 31)),
]
ROW_PAST_GAP = [Leg(x(ROW, 43)), Leg(x(ROW, 47), jump=True), Leg(x(ROW, 78))]
DASH_ACROSS = Leg(x(ROW, 41), jump=True, dash=True, dash_age=8)


def test_wake_climbs_through_well_climb_and_crosses_lamp_row(ctx: GameContext):
    entered: list[str] = []
    lit: list[BeaconLit] = []
    lamps: list[LampLit] = []
    collected: list[Collected] = []
    ctx.bus.subscribe(RoomEntered, lambda event: entered.append(event.room))
    ctx.bus.subscribe(BeaconLit, lit.append)
    ctx.bus.subscribe(LampLit, lamps.append)
    ctx.bus.subscribe(Collected, collected.append)
    run(ctx, "Wake", *wake(), walk(*ROW_TO_GAP, DASH_ACROSS, *ROW_PAST_GAP), ticks=3000)
    assert entered[0] == "Well_Climb"
    assert entered[-1] == "Lamp_Row"
    assert len(lit) == 1
    assert len(lamps) == 1
    assert collected


def test_the_cracked_wall_in_well_climb_opens_onto_old_guild(ctx: GameContext):
    broken: list[Broken] = []
    granted: list[Granted] = []
    ctx.bus.subscribe(Broken, broken.append)
    ctx.bus.subscribe(Granted, granted.append)
    run(
        ctx,
        "Well_Climb",
        climb(LEDGE, 1, lambda scene: scene.motor.grounded and scene.body.bottom <= LEDGE + 1),
        walk(
            Leg(x(WELL, 11)),
            Leg(x(WELL, 11), swing=True),
            Leg(x(GUILD, 3)),
            until=in_room("Old_Guild"),
        ),
        walk(Leg(x(GUILD, 10)), Leg(x(GUILD, 14), jump=True)),
        ticks=3000,
    )
    assert len(broken) == 1
    assert [(g.thing, g.count) for g in granted] == [("shard", 1)]


def test_a_new_game_starts_on_the_floor_of_wake(ctx: GameContext):
    scene = GameplayScene(ctx)
    assert scene.room == "Wake"
    assert scene.body.bottom == at(WAKE, 0, 20)[1]
    assert scene.body.center_x == x(WAKE, 4)


def test_lamp_row_has_four_dead_lamps_and_two_clockrats(ctx: GameContext):
    scene = GameplayScene(ctx, room="Lamp_Row")
    room = scene.rooms.graph.rects["Lamp_Row"]

    def inside(eid: EntityId) -> bool:
        body = scene.world.get(eid, Body)
        return room.collidepoint(body.center_x, body.y + body.height / 2)

    assert [lamp.lit for eid, lamp in scene.world.query(Lamp) if inside(eid)] == [False] * 4
    kinds = [brain.kind for eid, brain in scene.world.query(Brain) if inside(eid)]
    assert kinds == ["clockrat"] * 2


def test_the_water_gap_in_lamp_row_cannot_be_jumped(ctx: GameContext):
    with pytest.raises(AssertionError, match="died"):
        run(ctx, "Lamp_Row", walk(*ROW_TO_GAP, Leg(x(ROW, 41), jump=True)))
