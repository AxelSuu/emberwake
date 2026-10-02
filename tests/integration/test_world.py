"""Bots that play the greybox world's mechanisms through the gameplay scene."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, MarkerSpec, RoomFile, Source, make_room, read_toml

from emberwake.engine.input.replay import Replay
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game import paths
from emberwake.game.interact import Collected
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.game.context import GameContext

STEP = 1 / 60
HALL_X = 65 * 320
"""Lever_Hall's left edge in world px; its door is at tile 10."""


def play(
    ctx: GameContext, room: str, runs: list[tuple[int, list[str]]], world_path: Path | None = None
) -> GameplayScene:
    replay = Replay(room, 0, runs)
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room, replay=replay, world_path=world_path)
    scenes.push(scene)
    for _ in range(replay.ticks):
        scenes.update(STEP)
    return scene


def door(scene: GameplayScene) -> Door:
    (found,) = [door for _, door in scene.world.query(Door)]
    return found


def prefabs(scene: GameplayScene) -> list[str]:
    return sorted(identity.prefab for _, identity in scene.world.query(Identity))


def test_closed_door_blocks_the_hall(ctx: GameContext):
    scene = play(ctx, "Lever_Hall", [(5, []), (60, ["right"])])
    assert not door(scene).open
    assert scene.body.x + scene.body.width <= HALL_X + 10 * 16


def test_lever_opens_the_door_and_the_ember_is_collected_once(ctx: GameContext):
    collected: list[Collected] = []
    ctx.bus.subscribe(Collected, collected.append)
    runs = [(5, []), (8, ["right"]), (2, ["interact"]), (80, ["right"])]
    scene = play(ctx, "Lever_Hall", runs)
    assert door(scene).open
    assert scene.body.x > HALL_X + 16 * 16
    assert len(collected) == 1
    assert collected[0].iid in scene.spawner.state.removed
    scene.reload()
    for _ in range(2):
        scene.update(STEP)
    assert "ember" not in prefabs(scene)
    assert len(collected) == 1


def test_pressure_plate_holds_the_door(ctx: GameContext, tmp_path: Path):
    wall, inside, doorway = "#" * 20, "#" + "." * 18 + "#", "#.........b........#"
    rows = [wall, *[inside] * 6, doorway, doorway, "#.P...p...b........#", wall]
    marks = RoomFile(
        entities={"p": MarkerSpec("PressurePlate", {"Targets": ["b"]}), "b": MarkerSpec("Door")}
    )
    defs = read_toml(Defs, paths.levels("src/defs.toml"))
    project = build_project(Source(defs, [make_room("Plate", (0, 0), "\n".join(rows), marks)]))
    path = tmp_path / "world.ldtk"
    path.write_text(json.dumps(project))
    stand = [(5, []), (25, ["right"]), (10, [])]
    assert door(play(ctx, "Plate", stand, path)).open
    step_off = [*stand, (10, ["left"]), (5, [])]
    assert not door(play(ctx, "Plate", step_off, path)).open
