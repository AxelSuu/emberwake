"""Bots that walk the Underways from the Tinker's Nook down to the foot of the Cistern Shaft."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.test_greybox import STEP, Leg, Phase, at, in_room, run, walk
from tests.integration.test_tinker import at_the_tinker, pick, talk

from emberwake.engine.input.replay import Replay
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.rooms import RoomEntered
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

NOOK = (6, 8)
CELLAR = (5, 9)
HALL = (4, 10)
SHAFT = (4, 11)


def x(cell: tuple[int, int], col: float) -> float:
    return at(cell, col)[0]


def nook() -> Phase:
    return walk(Leg(x(NOOK, 11.5)), Leg(x(NOOK, 11.5), down=True), until=in_room("Gloom_Cellar"))


def to_the_corridor() -> list[Leg]:
    """Down off the stair, light the brazier, and fight west to the corridor under the slab."""
    return [
        Leg(x(CELLAR, 26.0)),
        Leg(x(CELLAR, 25.5)),
        Leg(x(CELLAR, 25.5), swing=True),
        Leg(x(CELLAR, 8.0), fight=True, limit=900),
        Leg(x(CELLAR, 3.5), fight=True, limit=400),
    ]


def cellar() -> Phase:
    return walk(*to_the_corridor(), Leg(x(CELLAR, -1.0)), until=in_room("Lever_Hall"))


def hall() -> Phase:
    return walk(
        Leg(x(HALL, 15.5)),
        Leg(x(HALL, 15.5), interact=True),
        Leg(x(HALL, 2.5), fight=True, limit=900),
        Leg(x(HALL, 2.5), down=True),
        until=in_room("Cistern_Shaft"),
    )


def shaft() -> Phase:
    return walk(
        Leg(x(SHAFT, 12.5)),
        Leg(x(SHAFT, 16.5)),
        Leg(x(SHAFT, 16.5), down=True),
        Leg(x(SHAFT, 3.5), fight=True, limit=900),
        Leg(x(SHAFT, 3.5), interact=True),
        Leg(x(SHAFT, 16.0), fight=True, limit=900),
        Leg(x(SHAFT, 18.5)),
    )


def test_the_underways_are_walked_from_the_nook_to_the_shaft_exit(ctx: GameContext):
    entered: list[str] = []
    ctx.bus.subscribe(RoomEntered, lambda event: entered.append(event.room))
    scene = run(ctx, "Tinkers_Nook", nook(), cellar(), hall(), shaft(), ticks=4000)
    assert entered == ["Gloom_Cellar", "Lever_Hall", "Cistern_Shaft"]
    assert scene.body.center_x > x(SHAFT, 18)
    doors = [door for _, door in scene.world.query(Door)]
    assert doors
    assert all(door.open for door in doors)


def lost_light() -> Phase:
    hops = [(33.5, 30.5), (31.0, 35.0), (34.0, 30.0), (32.5, 35.0), (34.5, 31.5)]
    climb = [
        leg
        for start, end in hops
        for leg in (Leg(x(CELLAR, start)), Leg(x(CELLAR, end), jump=True))
    ]
    return walk(
        *to_the_corridor(),
        Leg(x(CELLAR, 32.5), fight=True, limit=900),
        Leg(x(CELLAR, 35.5), jump=True),
        *climb,
        Leg(x(CELLAR, 31.5), jump=True),
        Leg(x(NOOK, 14.5), jump=True),
        Leg(x(NOOK, 20.0)),
        until=lambda scene: bool(scene.progress.data.flags.get("lost_light_gloom_cellar")),
    )


def test_a_lost_light_is_led_up_the_cellar_to_the_nook_beacon(ctx: GameContext):
    scene = run(ctx, "Tinkers_Nook", nook(), lost_light(), ticks=4000)
    assert scene.progress.data.flags["lost_lights"] == 1


def shove(
    ctx: GameContext, room: str, cell: tuple[int, int], col: float, side: str
) -> GameplayScene:
    """Stand in `room` at tile `col` and push `side` for four seconds."""
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room, replay=Replay(room, 0, [(240, [side])]))
    scenes.push(scene)
    scenes.apply_pending()
    scene.body.x = x(cell, col)
    for _ in range(240):
        scenes.update(STEP)
    return scene


def doors(scene: GameplayScene) -> list[Door]:
    return [door for _, door in scene.world.query(Door)]


def test_the_barred_door_east_of_the_nook_stays_shut(ctx: GameContext):
    scene = shove(ctx, "Tinkers_Nook", NOOK, 30.0, "right")
    assert not any(door.open for door in doors(scene))
    assert scene.body.x + scene.body.width <= x(NOOK, 38) + 1


def test_the_lever_hall_door_is_shut_until_the_lever_is_pulled(ctx: GameContext):
    scene = shove(ctx, "Lever_Hall", HALL, 14.0, "left")
    assert not any(door.open for door in doors(scene))
    assert scene.body.x >= x(HALL, 11) - 1


def test_the_nook_tinker_gives_flares_on_the_first_talk(ctx: GameContext):
    scenes, game = at_the_tinker(ctx, "Tinkers_Nook")
    assert not game.loadout.has("flare")
    talk(scenes)
    assert game.loadout.has("flare")
    pick(scenes, "Goodbye")
