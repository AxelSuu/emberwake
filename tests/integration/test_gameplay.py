from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame
import pytest

from emberwake.engine.input.replay import Replay
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.scene import SceneManager
from emberwake.game.player.controller import Dashed, Died
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.engine.platform.display import Display
    from emberwake.game.context import GameContext

STEP = 1 / 60
# Run right, jump the spike pit, keep running to the step.
RUN_AND_JUMP = Replay(
    "Test_Room", 0, [(5, []), (50, ["right"]), (14, ["jump", "right"]), (40, ["right"])]
)
PIT_RIGHT_EDGE = 20 * 16


def play(ctx: GameContext, replay: Replay, ticks: int) -> GameplayScene:
    """Headless helper: run a gameplay scene for `ticks` ticks driven by `replay`."""
    scenes = SceneManager()
    scene = GameplayScene(ctx, replay=replay)
    scenes.push(scene)
    for _ in range(ticks):
        scenes.update(STEP)
    return scene


def test_replays_are_deterministic(ctx: GameContext):
    a = play(ctx, RUN_AND_JUMP, RUN_AND_JUMP.ticks)
    b = play(ctx, RUN_AND_JUMP, RUN_AND_JUMP.ticks)
    assert (a.body, a.motor.vx, a.motor.vy) == (b.body, b.motor.vx, b.motor.vy)
    assert a.body.x > PIT_RIGHT_EDGE
    assert not a.motor.dead


def test_recording_matches_the_input_it_was_given(ctx: GameContext):
    scene = play(ctx, RUN_AND_JUMP, RUN_AND_JUMP.ticks)
    assert scene.recorder.replay.runs == RUN_AND_JUMP.runs


def test_switches_to_live_input_when_replay_ends(ctx: GameContext):
    scene = play(ctx, Replay("Test_Room", 0, [(3, ["right"])]), 10)
    assert scene.replay is None


def test_dash_triggers_hitstop(ctx: GameContext):
    scene = play(ctx, Replay("Test_Room", 0, [(5, []), (1, ["dash"])]), 6)
    assert scene.hitstop == scene.feel.juice.dash_hitstop
    body = scene.body.x
    scene.update(STEP)
    assert scene.body.x == body


def test_death_respawns_at_start(ctx: GameContext):
    died: list[Died] = []
    ctx.bus.subscribe(Died, died.append)
    walk_into_pit = Replay("Test_Room", 0, [(5, []), (60, ["right"]), (100, [])])
    scene = play(ctx, walk_into_pit, 90)
    assert died
    juice = scene.feel.juice
    for _ in range(juice.death_hitstop + juice.respawn_delay + 2):
        scene.update(STEP)
    assert scene.respawn_in == 0
    assert not scene.motor.dead
    assert scene.body.center_x == pytest.approx(scene.spawn_point[0])


def test_unsubscribes_on_exit(ctx: GameContext):
    scenes = SceneManager()
    scenes.push(GameplayScene(ctx))
    scenes.apply_pending()
    scenes.pop()
    scenes.apply_pending()
    ctx.bus.publish(Dashed(0, 0, 1, 0))


def test_draws_with_and_without_colliders(ctx: GameContext, display: Display):
    scene = play(ctx, RUN_AND_JUMP, 30)
    scene.draw(display.canvas, 0.5)
    scene.show_colliders = True
    scene.draw(display.canvas, 0.5)


def key(scene: GameplayScene, k: int) -> None:
    scene.handle(pygame.Event(pygame.KEYDOWN, key=k, mod=0))


def test_dev_keys(ctx: GameContext):
    scene = play(ctx, RUN_AND_JUMP, 1)
    key(scene, pygame.K_p)
    x = scene.body.x
    for _ in range(5):
        scene.update(STEP)
    assert scene.body.x == x
    key(scene, pygame.K_PERIOD)
    scene.update(STEP)
    key(scene, pygame.K_F2)
    key(scene, pygame.K_F3)
    assert scene.show_colliders
    assert scene.free_camera
    key(scene, pygame.K_F5)
    key(scene, pygame.K_F9)
    storage = ctx.storage
    assert isinstance(storage, MemoryStorage)
    (saved,) = [k for k in storage.data if k.startswith("replays/")]
    assert json.loads(storage.data[saved])["version"] == 1


def test_dev_keys_ignored_without_dev(ctx: GameContext):
    ctx.dev = False
    scene = play(ctx, RUN_AND_JUMP, 1)
    key(scene, pygame.K_p)
    assert not scene.time.paused
