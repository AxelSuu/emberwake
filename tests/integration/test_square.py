"""Bots through the Plate Room, the Photocell Gallery, Market Square and the Trial Gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.test_greybox import STEP, Leg, Phase, at, run, walk

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.actions import Action
from emberwake.game.crates import PushCrate
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

PLATE = (5, 12)
GALLERY = (7, 10)
SQUARE = (8, 8)
GATE = (12, 8)


def x(cell: tuple[int, int], col: float) -> float:
    return at(cell, col + 0.5)[0]


def inside(scene: GameplayScene, body: Body) -> bool:
    room = scene.rooms.graph.rects[scene.room]
    return room.collidepoint(body.center_x, body.y + body.height / 2)


def plate_room() -> list:
    return [
        walk(Leg(x(PLATE, 30), limit=900), Leg(x(PLATE, 38), limit=400)),
    ]


def test_the_crate_is_pushed_into_the_dip_to_open_the_plate_room_door(ctx: GameContext):
    scene = run(ctx, "Plate_Room", *plate_room(), ticks=1500)
    assert scene.body.center_x > x(PLATE, 35)
    doors = [door for _, body, door in scene.world.query(Body, Door) if inside(scene, body)]
    assert len(doors) == 1
    assert doors[0].open
    crates = [body for _, body, _ in scene.world.query(Body, PushCrate)]
    assert len(crates) == 1
    assert x(PLATE, 21) < crates[0].center_x < x(PLATE, 25)


def start(ctx: GameContext, room: str) -> GameplayScene:
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room)
    scenes.push(scene)
    scenes.apply_pending()
    scenes.update(STEP)
    return scene


def test_the_plate_room_door_is_shut_until_the_crate_is_on_the_plate(ctx: GameContext):
    scene = start(ctx, "Plate_Room")
    doors = [door for _, body, door in scene.world.query(Body, Door) if inside(scene, body)]
    assert len(doors) == 1
    assert not doors[0].open


def scripted(runs: list[tuple[int, list[str]]]) -> Phase:
    return Phase(lambda scene: ReplayPlayer(Replay(scene.room, 0, runs), Action))


def gallery_stage_one() -> list[Leg]:
    return [
        Leg(x(GALLERY, 13)),
        Leg(x(GALLERY, 15.5), jump=True),
        Leg(x(GALLERY, 21.5), jump=True),
        Leg(x(GALLERY, 25)),
        Leg(x(GALLERY, 48)),
        Leg(x(GALLERY, 50.5), jump=True),
        Leg(x(GALLERY, 48.5), jump=True),
        Leg(x(GALLERY, 46.8)),
        Leg(x(GALLERY, 43.5), jump=True),
    ]


def arm(scene: GameplayScene) -> ReplayPlayer[Action]:
    scene.loadout.give("flare")
    return ReplayPlayer(Replay(scene.room, 0, [(1, [])]), Action)


def gallery_stage_two() -> list[Phase]:
    return [
        walk(Leg(x(GALLERY, 36.5))),
        Phase(arm),
        scripted([(1, ["flare"]), (20, [])]),
        walk(
            Leg(x(GALLERY, 29.5), jump=True),
            Leg(x(GALLERY, 6.5)),
            Leg(x(GALLERY, 3), jump=True),
            Leg(x(GALLERY, 6), jump=True),
            Leg(x(GALLERY, 2.5), jump=True),
            Leg(x(GALLERY, 4)),
            Leg(x(GALLERY, 9.5), jump=True),
        ),
    ]


def gallery_stage_three() -> Phase:
    return walk(
        Leg(x(GALLERY, 13)),
        Leg(x(GALLERY, 24), jump=True, dash=True, dash_age=8),
        Leg(x(GALLERY, 23)),
        Leg(x(GALLERY, 26), jump=True),
        Leg(x(GALLERY, 31), jump=True),
        Leg(x(GALLERY, 30), jump=True),
    )


def test_the_gallery_is_climbed_to_its_top(ctx: GameContext):
    scene = run(
        ctx,
        "Photocell_Gallery",
        walk(*gallery_stage_one()),
        *gallery_stage_two(),
        gallery_stage_three(),
        ticks=4000,
    )
    assert scene.body.bottom < at(GALLERY, 0, 5)[1]


def test_the_gallery_door_is_shut_until_a_flare_lights_the_photocell(ctx: GameContext):
    scene = start(ctx, "Photocell_Gallery")
    doors = [door for _, body, door in scene.world.query(Body, Door) if inside(scene, body)]
    assert len(doors) == 1
    assert not doors[0].open
