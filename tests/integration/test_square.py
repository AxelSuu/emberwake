"""Bots through the Plate Room, the Photocell Gallery, Market Square and the Trial Gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.test_greybox import STEP, Leg, at, run, walk

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
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
