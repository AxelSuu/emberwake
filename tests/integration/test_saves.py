"""Relight a beacon, quit, continue: the world comes back as it was left."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.actions import Action
from emberwake.game.beacons import Beacon
from emberwake.game.data.save import SaveSlot, load_slot, save_slot, slot_key
from emberwake.game.interact import Switch
from emberwake.game.scenes.gameplay import DEFAULT_ROOM, GameplayScene
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
TO_BEACON = [(5, []), (20, ["right"]), (2, ["interact"]), (5, [])]
"""From the start of Wake to its beacon, then relight it."""


@pytest.fixture
def storage(ctx: GameContext) -> MemoryStorage:
    assert isinstance(ctx.storage, MemoryStorage)
    return ctx.storage


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    scene = GameplayScene(ctx)
    scenes.push(scene)
    scenes.apply_pending()
    return scenes, scene


def drive(scenes: SceneManager, scene: GameplayScene, runs: list[tuple[int, list[str]]]) -> None:
    """Feed scripted input to a scene that continues from the slot."""
    replay = Replay(scene.room, 0, runs)
    scene.replay = ReplayPlayer(replay, Action)
    for _ in range(replay.ticks):
        scenes.update(STEP)


def entity[T](scene: GameplayScene, prefab: str, tp: type[T]) -> T | None:
    """The `tp` component of the active room's `prefab` entity, if there is one."""
    found = [
        scene.world.find(eid, tp)
        for eid, identity in scene.world.query(Identity)
        if identity.prefab == prefab and identity.room == scene.room
    ]
    return found[0] if found else None


def test_an_empty_slot_starts_a_new_game(ctx: GameContext, storage: MemoryStorage):
    scenes, scene = start(ctx)
    assert scene.room == DEFAULT_ROOM
    assert load_slot(storage, ctx.slot) is None
    scenes.close()
    saved = load_slot(storage, ctx.slot)
    assert saved is not None
    assert (saved.room, saved.beacon) == (DEFAULT_ROOM, "")


def test_relighting_saves_and_continues_at_the_beacon(ctx: GameContext, storage: MemoryStorage):
    scenes, scene = start(ctx)
    drive(scenes, scene, TO_BEACON)
    beacon = entity(scene, "beacon", Beacon)
    assert beacon is not None
    assert beacon.lit
    assert scene.flash.left > 0
    assert scene.backdrops.warmth > 0
    saved = load_slot(storage, ctx.slot)
    assert saved is not None
    assert saved.room == DEFAULT_ROOM
    identities = [identity for _, identity in scene.world.query(Identity)]
    here = [i.iid for i in identities if i.prefab == "beacon" and i.room == DEFAULT_ROOM]
    assert [saved.beacon] == here
    assert saved.playtime > 0
    scenes.close()

    _, again = start(ctx)
    lit = entity(again, "beacon", Beacon)
    assert lit is not None
    assert lit.lit
    assert again.body.center_x == pytest.approx(8 * 16 + 8)
    assert again.progress.data.discovered == [again.rooms.graph.levels[DEFAULT_ROOM].iid]


def test_quitting_keeps_progress_but_not_position(ctx: GameContext, storage: MemoryStorage):
    save_slot(storage, ctx.slot, SaveSlot(room="Lab_Lever_Hall"))
    scenes, scene = start(ctx)
    drive(scenes, scene, [(5, []), (8, ["right"]), (2, ["interact"]), (80, ["right"])])
    assert scene.progress.data.stats.embers == 1
    scenes.close()

    scenes, again = start(ctx)
    scenes.update(STEP)
    switch = entity(again, "lever", Switch)
    door = entity(again, "door", Door)
    assert switch is not None
    assert switch.on
    assert door is not None
    assert door.open
    assert "ember" not in {i.prefab for _, i in again.world.query(Identity)}
    assert again.body.center_x == pytest.approx(65 * 320 + 3 * 16 + 8)
    assert again.progress.data.stats.embers == 1


def test_new_game_ignores_the_slot_once(ctx: GameContext, storage: MemoryStorage):
    save_slot(storage, ctx.slot, SaveSlot(room="Lab_Lever_Hall"))
    ctx.new_game = True
    _, scene = start(ctx)
    assert scene.room == DEFAULT_ROOM
    assert not ctx.new_game


def test_explicit_rooms_and_replays_never_save(ctx: GameContext, storage: MemoryStorage):
    scenes = SceneManager()
    scenes.push(GameplayScene(ctx, room="Lab_Lever_Hall"))
    scenes.push(GameplayScene(ctx, replay=Replay(DEFAULT_ROOM, 0, [(1, [])])))
    scenes.apply_pending()
    scenes.close()
    assert slot_key(ctx.slot) not in storage.data
