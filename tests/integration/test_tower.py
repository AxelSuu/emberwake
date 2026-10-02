"""Belfry, Clocktower_Stair and Clock_Face: the climb up the tower, lamps, bell and the King."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.test_greybox import (
    STEP,
    Climber,
    Leg,
    Phase,
    Route,
    at,
    climb,
    in_room,
    walk,
)

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Body, Tile
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.actions import Action
from emberwake.game.beacons import BeaconLit
from emberwake.game.combat import Health
from emberwake.game.encounters import Encounter, EncounterCleared, EncounterStarted
from emberwake.game.enemies import Brain, Minion
from emberwake.game.grants import Granted
from emberwake.game.lamps import Lamp
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.switches import Bell

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.game.context import GameContext

BELFRY = (8, 6)
STAIR = (8, 2)
FACE = (8, 0)
NEVER = -1e9
"""A climber with no top keeps bouncing until the phase's own condition holds."""

type Spot = tuple[tuple[int, int], int, int]


def x(cell: tuple[int, int], col: float) -> float:
    return at(cell, col)[0]


def stand(scene: GameplayScene, cell: tuple[int, int], col: int, row: int) -> None:
    """Put the player on the floor of tile (col, row) of the room at `cell`."""
    px, py = at(cell, col + 0.5, row + 1)
    body = scene.body
    body.x, body.y = px - body.width / 2, py - body.height
    scene.motor.previous = (body.x, body.y)
    scene.world.get(scene.player, Health).invulnerable = 1e9


def play(
    ctx: GameContext, room: str, *phases: Phase, tile: Spot | None = None, ticks: int = 2000
) -> GameplayScene:
    """Run the phases from the room's first PlayerStart, or from `tile` (cell, col, row)."""
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room, replay=Replay(room))
    scenes.push(scene)
    scenes.apply_pending()
    if tile:
        stand(scene, *tile)
    route = Route(scene, list(phases))
    scene.replay = route
    for _ in range(ticks):
        scenes.update(STEP)
        assert not scene.motor.dead, f"died at {scene.body.center_x:.0f},{scene.body.y:.0f}"
        if route.finished:
            return scene
    where = f"{scene.body.center_x:.0f},{scene.body.y:.0f}"
    msg = f"{scene.room}: stuck in phase {route.index} at {where}"
    raise AssertionError(msg)


def above(row: float, cell: tuple[int, int] = BELFRY):
    return lambda scene: scene.body.bottom <= at(cell, 0, row)[1]


def stair_climb() -> Phase:
    return climb(NEVER, 1, above(2.5, STAIR))


class ShaftTop(Climber):
    """Climbs until a hop ends high above the floor on the exit side, then walks out."""

    def sample(self) -> frozenset[Action]:
        body = self.scene.body
        if body.bottom <= at(FACE, 0, 18.5)[1] and body.center_x > x(FACE, 11.5):
            self.out = True
        return super().sample()


def to_the_face() -> Phase:
    """Out of the stair's top and onto the Face's floor, heading for the arena."""
    return Phase(
        lambda scene: ShaftTop(scene, NEVER, 1), lambda scene: scene.body.center_x > x(FACE, 15)
    )


def belfry_climb() -> list[Phase]:
    c = lambda col: x(BELFRY, col + 0.5)  # noqa: E731
    return [
        walk(
            Leg(c(22), jump=True),
            Leg(c(26)),
            Leg(c(31), jump=True),
            Leg(c(29)),
            Leg(c(24), jump=True),
            Leg(c(21)),
            Leg(c(17), jump=True),
            Leg(c(9)),
            Leg(c(9), jump=True),
        ),
        climb(NEVER, 1, in_room("Clocktower_Stair")),
    ]


def test_the_belfry_is_climbed_from_its_floor_to_the_chimney(ctx: GameContext) -> None:
    play(ctx, "Belfry", *belfry_climb(), tile=(BELFRY, 27, 20))


SWING = [(1, ["right"]), (12, ["swing"]), (10, [])]


def drive(scene: GameplayScene, runs: list[tuple[int, list[str]]]) -> None:
    replay = Replay(scene.room, 0, runs)
    scene.replay = ReplayPlayer(replay, Action)
    for _ in range(replay.ticks):
        scene.manager.update(STEP)


def start(ctx: GameContext, room: str) -> GameplayScene:
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room)
    scenes.push(scene)
    scenes.apply_pending()
    scenes.update(STEP)
    scene.world.get(scene.player, Health).invulnerable = 1e9
    return scene


def swing_left_of(scene: GameplayScene, target: Body) -> None:
    scene.body.x, scene.body.y = target.x - 14, target.bottom - scene.body.height
    drive(scene, SWING)


def lamps(scene: GameplayScene) -> list[tuple[Body, Lamp]]:
    return sorted(((b, lamp) for _, b, lamp in scene.world.query(Body, Lamp)), key=lambda r: r[0].x)


def wisps(scene: GameplayScene) -> list[tuple[EntityId, Body]]:
    rows = scene.world.query(Body, Brain)
    return [(eid, body) for eid, body, brain in rows if brain.kind == "wisp_eater"]


def test_the_belfry_has_three_lamps_two_wisp_eaters_and_a_bell(ctx: GameContext) -> None:
    scene = start(ctx, "Belfry")
    assert len(lamps(scene)) == 3
    assert len(wisps(scene)) == 2
    assert len(list(scene.world.query(Bell))) == 1


def test_a_lamp_the_player_lights_is_snuffed_by_a_wisp_eater(ctx: GameContext) -> None:
    scene = start(ctx, "Belfry")
    body, lamp = lamps(scene)[1]
    swing_left_of(scene, body)
    assert lamp.lit
    stand(scene, BELFRY, 27, 20)
    drive(scene, [(60 * 20, [])])
    assert not lamp.lit


def test_the_bell_stuns_the_wisp_eaters_near_it(ctx: GameContext) -> None:
    scene = start(ctx, "Belfry")
    ((_, bell_body),) = [(e, b) for e, b, _ in scene.world.query(Body, Bell)]
    (eid, wisp_body), _ = wisps(scene)
    wisp_body.x, wisp_body.y = bell_body.x - 30, bell_body.y - 20
    swing_left_of(scene, bell_body)
    assert scene.world.get(eid, Brain).stagger > 0


def test_quill_stands_in_the_belfry_at_stage_zero(ctx: GameContext) -> None:
    scene = start(ctx, "Belfry")
    quills = [i for _, i in scene.world.query(Identity) if i.prefab == "quill"]
    assert len(quills) == 1


def test_the_stair_is_climbed_by_wall_jumps_past_its_gearbugs(ctx: GameContext) -> None:
    play(ctx, "Belfry", *belfry_climb(), stair_climb(), tile=(BELFRY, 27, 20), ticks=4000)


POGO = [(2, []), (14, ["jump"]), (6, ["left"]), (8, ["left", "down", "swing"]), (30, ["left"])]


def test_a_down_swing_on_the_spike_bulb_reaches_the_lost_light(ctx: GameContext) -> None:
    scene = start(ctx, "Clocktower_Stair")
    stand(scene, STAIR, 6, 30)
    drive(scene, POGO)
    assert not scene.motor.dead
    assert scene.motor.grounded
    assert scene.body.bottom == at(STAIR, 0, 27)[1]
    lights = [i for _, i in scene.world.query(Identity) if i.prefab == "lost_light"]
    assert len(lights) == 1


def test_the_stair_has_two_gearbugs(ctx: GameContext) -> None:
    scene = start(ctx, "Clocktower_Stair")
    bugs = [b for _, b in scene.world.query(Brain) if b.kind == "gearbug"]
    assert len(bugs) == 2


def solid(scene: GameplayScene, col: int, row: int) -> bool:
    rect = scene.rooms.graph.rects[scene.room]
    return scene.grid.get(rect.x // 16 + col, rect.y // 16 + row) == Tile.SOLID


def wave(scene: GameplayScene) -> list[EntityId]:
    owners = {eid for eid, _ in scene.world.query(Encounter)}
    return [eid for eid, _, m in scene.world.query(Brain, Minion) if m.owner in owners]


def kill_wave(scene: GameplayScene) -> None:
    for eid in wave(scene):
        scene.world.get(eid, Health).dead = True
    drive(scene, [(6, [])])


def test_the_tower_is_climbed_to_the_face_and_the_king_clears_the_way_to_lamp_a(
    ctx: GameContext,
) -> None:
    started: list[EncounterStarted] = []
    cleared: list[EncounterCleared] = []
    lit: list[BeaconLit] = []
    ctx.bus.subscribe(EncounterStarted, started.append)
    ctx.bus.subscribe(EncounterCleared, cleared.append)
    ctx.bus.subscribe(BeaconLit, lit.append)
    scene = play(
        ctx,
        "Belfry",
        *belfry_climb(),
        stair_climb(),
        to_the_face(),
        tile=(BELFRY, 27, 20),
        ticks=5000,
    )
    assert scene.room == "Clock_Face"
    assert not started
    assert solid(scene, 34, 18)
    assert not solid(scene, 10, 20)

    drive(scene, [(40, ["right"])])
    assert started
    assert solid(scene, 10, 20)
    assert solid(scene, 34, 18)
    kill_wave(scene)
    drive(scene, [(90, [])])
    assert any(b.kind == "clockrat_king" for _, b in scene.world.query(Brain))
    kill_wave(scene)
    drive(scene, [(20, [])])
    assert cleared
    assert not solid(scene, 10, 20)
    assert not solid(scene, 34, 18)

    scene.body.x = x(FACE, 37.5) - scene.body.width / 2
    scene.body.y = at(FACE, 0, 20)[1] - scene.body.height
    drive(scene, [(3, []), (2, ["interact"]), (5, [])])
    assert len(lit) == 1


SHARD_ROUTE = [
    (2, []),
    (14, ["left", "jump"]),
    (10, ["left"]),
    (6, ["left", "down", "swing"]),
    (8, ["left"]),
    (6, ["left", "down", "swing"]),
    (40, ["left"]),
]


def test_two_pogos_off_the_spike_bulbs_reach_lantern_shard_3(ctx: GameContext) -> None:
    granted: list[Granted] = []
    ctx.bus.subscribe(Granted, granted.append)
    scene = start(ctx, "Clock_Face")
    stand(scene, FACE, 15, 7)
    drive(scene, SHARD_ROUTE)
    assert not scene.motor.dead
    assert [(g.thing, g.count) for g in granted] == [("shard", 1)]


def test_a_jump_and_a_dash_do_not_cross_the_lamp_hook_gap(ctx: GameContext) -> None:
    scene = start(ctx, "Clock_Face")
    stand(scene, FACE, 15, 7)
    run_up = [(50, ["right"]), (14, ["right", "jump"]), (8, ["right"]), (3, ["right", "dash"])]
    drive(scene, [*run_up, (90, ["right"])])
    assert scene.body.bottom != at(FACE, 0, 8)[1]
