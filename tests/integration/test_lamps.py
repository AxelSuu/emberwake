"""Lamp_Lab: swing a lamp lit, hold it with a beacon, lose it to the Wisp-eater, keep it saved."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.actions import Action
from emberwake.game.beacons import Beacon
from emberwake.game.data.save import SaveSlot, save_slot
from emberwake.game.enemies import Brain
from emberwake.game.lamps import Lamp
from emberwake.game.light import LightSource
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
SWING = [(1, ["right"]), (12, ["swing"]), (10, [])]


def start(ctx: GameContext, room: str | None = "Lamp_Lab") -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room)
    scenes.push(scene)
    scenes.apply_pending()
    scenes.update(STEP)
    return scenes, scene


def drive(scene: GameplayScene, runs: list[tuple[int, list[str]]]) -> None:
    replay = Replay(scene.room, 0, runs)
    scene.replay = ReplayPlayer(replay, Action)
    for _ in range(replay.ticks):
        scene.manager.update(STEP)


def lamps(scene: GameplayScene) -> list[Lamp]:
    """The room's lamps from left to right: a, b (loose), c, d (held by the beacon)."""
    rows = sorted(scene.world.query(Body, Lamp), key=lambda row: row[1].x)
    return [lamp for _, _, lamp in rows]


def lit(scene: GameplayScene) -> list[bool]:
    return [lamp.lit for lamp in lamps(scene)]


def stand_by(scene: GameplayScene, index: int) -> None:
    """Put the player just left of lamp `index`, on the floor."""
    rows = sorted(scene.world.query(Body, Lamp), key=lambda row: row[1].x)
    body = rows[index][1]
    scene.body.x, scene.body.y = body.x - 14, body.bottom - scene.body.height


def light_lamp(scene: GameplayScene, index: int) -> None:
    stand_by(scene, index)
    drive(scene, SWING)


def relight_beacon(scene: GameplayScene) -> None:
    (body,) = [b for _, b, _ in scene.world.query(Body, Beacon)]
    scene.body.x, scene.body.y = body.x, body.bottom - scene.body.height
    drive(scene, [(3, []), (2, ["interact"]), (5, [])])


def wisp(scene: GameplayScene) -> Body:
    (body,) = [b for _, b, brain in scene.world.query(Body, Brain) if brain.kind == "wisp_eater"]
    return body


def test_the_lab_has_four_dead_lamps_a_beacon_and_a_wisp_eater(ctx: GameContext) -> None:
    _, scene = start(ctx)
    assert lit(scene) == [False] * 4
    assert not list(scene.world.query(LightSource))
    assert wisp(scene) is not None


def test_a_swing_lights_a_lamp_and_it_lights_the_room(ctx: GameContext) -> None:
    _, scene = start(ctx)
    before = scene.light["lab"].lit
    light_lamp(scene, 0)
    assert lit(scene) == [True, False, False, False]
    assert len(list(scene.world.query(LightSource))) == 1
    assert scene.light["lab"].lit == before + 1
    assert scene.hud.banner_left > 0
    assert scene.hud.banner_sub.endswith("%")


def test_a_lit_lamp_survives_its_room_reloading(ctx: GameContext) -> None:
    scenes, scene = start(ctx)
    light_lamp(scene, 0)
    room = scene.rooms.loaded["Lamp_Lab"]
    scene.spawner.despawn_room(room)
    scene.world.flush()
    assert not lamps(scene)
    scene.spawner.spawn_room(room)
    scenes.update(STEP)
    scenes.update(STEP)
    assert lit(scene) == [True, False, False, False]
    assert len(list(scene.world.query(LightSource))) == 1


def test_lit_lamps_stay_lit_after_quitting_and_continuing(ctx: GameContext) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room="Lamp_Lab"))
    scenes, scene = start(ctx, room=None)
    light_lamp(scene, 1)
    scenes.close()

    _, again = start(ctx, room=None)
    assert lit(again) == [False, True, False, False]
    assert len(list(again.world.query(LightSource))) == 1
    assert again.light["lab"] == scene.light["lab"]


def test_a_lit_beacon_holds_the_lamps_it_is_linked_to(ctx: GameContext) -> None:
    _, scene = start(ctx)
    relight_beacon(scene)
    light_lamp(scene, 2)
    light_lamp(scene, 0)
    held = [lamp.protected for lamp in lamps(scene)]
    assert held == [False, False, True, False]


def test_a_lamp_lit_before_its_beacon_is_held_once_the_beacon_burns(ctx: GameContext) -> None:
    _, scene = start(ctx)
    light_lamp(scene, 3)
    assert not lamps(scene)[3].protected
    relight_beacon(scene)
    assert lamps(scene)[3].protected


def test_protection_is_saved_with_the_lamp(ctx: GameContext) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room="Lamp_Lab"))
    scenes, scene = start(ctx, room=None)
    relight_beacon(scene)
    light_lamp(scene, 2)
    scenes.close()

    _, again = start(ctx, room=None)
    assert [lamp.protected for lamp in lamps(again)] == [False, False, True, False]
    assert lit(again) == [False, False, True, False]


def test_a_wisp_eater_snuffs_a_lamp_you_left_burning(ctx: GameContext) -> None:
    _, scene = start(ctx)
    light_lamp(scene, 1)
    banner = scene.light["lab"]
    stand_by(scene, 0)
    drive(scene, [(400, [])])
    assert lit(scene) == [False] * 4
    assert scene.light["lab"].lit == banner.lit - 1


def send_wisp_to(scene: GameplayScene, index: int) -> None:
    """Park the Wisp-eater above lamp `index` and the player far from both."""
    lamp = lamp_body(scene, index)
    wisp(scene).x, wisp(scene).y = lamp.x, lamp.y - 40
    stand_by(scene, 0)


def lamp_body(scene: GameplayScene, index: int) -> Body:
    return sorted((b for _, b, _ in scene.world.query(Body, Lamp)), key=lambda b: b.x)[index]


def test_a_wisp_eater_snuffs_a_lamp_that_no_beacon_holds(ctx: GameContext) -> None:
    _, scene = start(ctx)
    light_lamp(scene, 2)
    send_wisp_to(scene, 2)
    drive(scene, [(300, [])])
    assert not any(lit(scene))


def test_a_snuffed_lamp_stays_dark_after_quitting_and_continuing(ctx: GameContext) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room="Lamp_Lab"))
    scenes, scene = start(ctx, room=None)
    light_lamp(scene, 1)
    scenes.close()

    scenes, scene = start(ctx, room=None)
    assert lit(scene)[1]
    stand_by(scene, 0)
    drive(scene, [(400, [])])
    assert not any(lit(scene))
    scenes.close()

    _, again = start(ctx, room=None)
    assert not any(lit(again))
    assert not list(again.world.query(LightSource))


def test_a_wisp_eater_cannot_snuff_a_held_lamp(ctx: GameContext) -> None:
    _, scene = start(ctx)
    relight_beacon(scene)
    light_lamp(scene, 2)
    send_wisp_to(scene, 2)
    drive(scene, [(300, [])])
    assert lit(scene)[2]
