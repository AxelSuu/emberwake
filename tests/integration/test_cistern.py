"""Sluice, Pump House, Rat Warren, Cistern Gate and Cistern: the way down to the Lamprey."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.test_greybox import Leg, Phase, at, in_room, walk
from tests.integration.test_square import arm, scripted
from tests.integration.test_tower import drive, kill_wave, play, solid, start, wave

from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.beacons import BeaconLit
from emberwake.game.encounters import EncounterCleared, EncounterStarted
from emberwake.game.grants import Granted
from emberwake.game.platforms import Platform

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.game.context import GameContext
    from emberwake.game.scenes.gameplay import GameplayScene

SQUARE = (8, 8)
GATE = (10, 10)
CISTERN = (10, 11)
SLUICE = (12, 9)
WARREN = (14, 10)
PUMP = (16, 9)


def c(cell: tuple[int, int]) -> Callable[[float], float]:
    """World x of the middle of a tile column in the room at `cell`."""
    return lambda col: at(cell, col + 0.5)[0]


def test_the_square_tunnel_leads_into_the_sluice(ctx: GameContext) -> None:
    sq = c(SQUARE)
    east = walk(Leg(sq(71)), Leg(sq(75), jump=True), Leg(c(SLUICE)(3)), until=in_room("Sluice"))
    scene = play(ctx, "Market_Square", east, tile=(SQUARE, 68, 20))
    assert scene.room == "Sluice"


def sluice_to_the_pit() -> list[Leg]:
    s = c(SLUICE)
    return [
        Leg(s(9)),
        Leg(s(21), jump=True, dash=True, dash_age=8),
        Leg(s(30)),
        Leg(s(30), interact=True),
        Leg(s(54), limit=600),
        Leg(s(58)),
    ]


def test_the_sluice_is_crossed_by_dash_valve_and_crate(ctx: GameContext) -> None:
    s = c(SLUICE)
    route = walk(
        *sluice_to_the_pit(),
        Leg(s(61)),
        Leg(s(65), jump=True),
        Leg(s(76), jump=True, dash=True, dash_age=8),
        Leg(c(PUMP)(3)),
        until=in_room("Pump_House"),
    )
    scene = play(ctx, "Sluice", route, tile=(SLUICE, 3, 7), ticks=3000)
    assert scene.room == "Pump_House"


def test_the_sluice_pit_drops_into_the_rat_warren(ctx: GameContext) -> None:
    s = c(SLUICE)
    down = walk(
        *sluice_to_the_pit(),
        Leg(s(61)),
        Leg(s(61), down=True),
        until=in_room("Rat_Warren"),
    )
    scene = play(ctx, "Sluice", down, tile=(SLUICE, 3, 7), ticks=3000)
    assert scene.room == "Rat_Warren"


def test_the_channel_too_wide_to_dash_holds_until_its_valve_is_turned(ctx: GameContext) -> None:
    scene = start(ctx, "Sluice")
    assert not solid(scene, 38, 8)
    s = c(SLUICE)
    scene = play(ctx, "Sluice", walk(Leg(s(30)), Leg(s(30), interact=True)), tile=(SLUICE, 24, 7))
    drive(scene, [(10, [])])
    assert solid(scene, 38, 8)


def test_the_pump_door_needs_the_crate_and_a_flare(ctx: GameContext) -> None:
    lit: list[BeaconLit] = []
    granted: list[Granted] = []
    ctx.bus.subscribe(BeaconLit, lit.append)
    ctx.bus.subscribe(Granted, granted.append)
    p = c(PUMP)
    scene = play(
        ctx,
        "Pump_House",
        walk(Leg(p(15)), Leg(p(16.5))),
        Phase(arm),
        scripted([(1, ["flare"]), (20, [])]),
        walk(Leg(p(24), jump=True), Leg(p(33)), Leg(p(33), interact=True), Leg(p(36))),
        tile=(PUMP, 3, 7),
    )
    assert len(lit) == 1
    assert scene.progress.data.flags["lamp_b"] == 1
    assert [g.thing for g in granted] == ["oil_flask"]


def test_without_a_flare_the_pump_door_stays_shut(ctx: GameContext) -> None:
    p = c(PUMP)
    route = walk(Leg(p(15)), Leg(p(16.5)), Leg(p(24), jump=True))
    scene = play(ctx, "Pump_House", route, tile=(PUMP, 3, 7))
    drive(scene, [(60, ["right"])])
    assert scene.body.center_x < p(29)


def test_the_warren_runs_three_waves_and_opens_the_way_to_shard_2(ctx: GameContext) -> None:
    started: list[EncounterStarted] = []
    cleared: list[EncounterCleared] = []
    granted: list[Granted] = []
    ctx.bus.subscribe(EncounterStarted, started.append)
    ctx.bus.subscribe(EncounterCleared, cleared.append)
    ctx.bus.subscribe(Granted, granted.append)
    w = c(WARREN)
    scene = play(ctx, "Rat_Warren", walk(Leg(w(28))), tile=(WARREN, 9, 9))
    drive(scene, [(10, [])])
    assert started
    assert solid(scene, 21, 0)
    for count in (1, 2, 2):
        drive(scene, [(90, [])])
        assert len(wave(scene)) == count
        kill_wave(scene)
    drive(scene, [(20, [])])
    assert cleared
    assert not solid(scene, 21, 0)
    assert not solid(scene, 5, 8)
    drive(scene, [(240, ["left"])])
    assert [g.thing for g in granted] == ["shard"]


def test_the_warren_ladder_climbs_back_to_the_sluice(ctx: GameContext) -> None:
    w = c(WARREN)
    up = walk(
        Leg(w(19), jump=True),
        Leg(w(15), jump=True),
        Leg(w(19), jump=True),
        Leg(w(21)),
        Leg(w(21), jump=True),
        until=in_room("Sluice"),
    )
    scene = play(ctx, "Rat_Warren", walk(Leg(w(16))), up, tile=(WARREN, 9, 9))
    assert scene.room == "Sluice"


def test_the_square_grate_drops_into_the_gate_and_its_ladder_climbs_back(
    ctx: GameContext,
) -> None:
    g = c(GATE)
    down = walk(Leg(c(SQUARE)(45.5), down=True), until=in_room("Cistern_Gate"))
    land = walk(Leg(g(2)))
    up = walk(
        Leg(g(5), jump=True),
        Leg(g(7)),
        Leg(g(9.5), jump=True),
        Leg(g(8.5)),
        Leg(g(6), jump=True),
        Leg(g(5.5)),
        Leg(g(5.5), jump=True),
        until=in_room("Market_Square"),
    )
    scene = play(ctx, "Market_Square", down, land, up, tile=(SQUARE, 45, 20), ticks=3000)
    assert scene.room == "Market_Square"


def test_the_gate_door_waits_for_both_quarter_lamps(ctx: GameContext) -> None:
    for flags in ({}, {"lamp_a": 1}, {"lamp_b": 1}):
        ctx.flags = flags
        scene = start(ctx, "Cistern_Gate")
        assert solid(scene, 24, 8), flags


def test_with_both_lamps_lit_the_gate_opens_down_into_the_cistern(ctx: GameContext) -> None:
    ctx.flags = {"lamp_a": 1, "lamp_b": 1}
    g = c(GATE)
    scene = play(
        ctx, "Cistern_Gate", walk(Leg(g(29.5)), until=in_room("Cistern")), tile=(GATE, 2, 9)
    )
    assert scene.room == "Cistern"


def lift(scene: GameplayScene) -> Body | None:
    return next((body for _, body, _ in scene.world.query(Body, Platform)), None)


def test_the_cistern_lift_waits_for_the_lamprey_to_die(ctx: GameContext) -> None:
    assert lift(start(ctx, "Cistern")) is None
    ctx.flags = {"lamprey_defeated": 1, "lamprey_drained": 1}
    scene = start(ctx, "Cistern")
    assert lift(scene) is not None


def test_after_the_lamprey_the_lift_carries_the_player_back_into_the_gate(
    ctx: GameContext,
) -> None:
    ctx.flags = {"lamprey_defeated": 1, "lamprey_drained": 1}
    scene = play(ctx, "Cistern", walk(Leg(c(CISTERN)(29))), tile=(CISTERN, 29, 12))
    top = at(CISTERN, 0, 1)[1]
    for _ in range(600):
        body = lift(scene)
        if body is not None and body.y <= top + 1:
            break
        drive(scene, [(1, [])])
    drive(scene, [(14, ["jump"]), (20, ["jump", "right"]), (30, ["right"])])
    assert scene.room == "Cistern_Gate"


def test_the_gate_and_the_cistern_each_hold_an_echo(ctx: GameContext) -> None:
    ctx.flags = {"lamprey_defeated": 1, "lamprey_drained": 1}
    for room in ("Cistern_Gate", "Cistern"):
        scene = start(ctx, room)
        rect = scene.rooms.graph.rects[room]
        echoes = [
            i.iid
            for _, body, i in scene.world.query(Body, Identity)
            if i.prefab == "echo" and rect.collidepoint(body.center_x, body.y)
        ]
        assert len(echoes) == 1, room
