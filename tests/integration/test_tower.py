"""Belfry, Clocktower_Stair and Clock_Face: the climb up the tower, lamps, bell and the King."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.test_greybox import STEP, Leg, Phase, Route, at, climb, walk

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.actions import Action
from emberwake.game.combat import Health
from emberwake.game.enemies import Brain
from emberwake.game.lamps import Lamp
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.switches import Bell

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.game.context import GameContext

BELFRY = (8, 6)

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
        climb(at(BELFRY, 0, 2)[1], 1, above(2.5)),
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
