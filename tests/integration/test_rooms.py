"""The gameplay scene in a three-room world built from text."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, Source, make_room, read_toml

from emberwake.engine.input.replay import Replay
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.rooms import RoomEntered
from emberwake.game import paths
from emberwake.game.player.controller import Died
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.engine.platform.display import Display
    from emberwake.game.context import GameContext

STEP = 1 / 60
TOP = "#" * 20
OPEN = "." * 20
FLOOR = "#" * 20
WEST = "\n".join([TOP, *["#" + "." * 19] * 8, "#.P" + "." * 17, FLOOR])
MIDDLE = "\n".join([TOP, *[OPEN] * 8, "..P" + "." * 17, "#" * 8 + "^^^^" + "#" * 8])
EAST = "\n".join([TOP, *["." * 19 + "#"] * 9, FLOOR])


@pytest.fixture
def world_path(tmp_path: Path) -> Path:
    defs = read_toml(Defs, paths.levels("src/defs.toml"))
    rooms = [
        make_room("West", (0, 0), WEST),
        make_room("Middle", (1, 0), MIDDLE),
        make_room("East", (2, 0), EAST),
    ]
    path = tmp_path / "world.ldtk"
    path.write_text(json.dumps(build_project(Source(defs, rooms))))
    return path


def play(ctx: GameContext, world_path: Path, runs: list[tuple[int, list[str]]]) -> GameplayScene:
    replay = Replay("West", 0, runs)
    scenes = SceneManager()
    scene = GameplayScene(ctx, room="West", replay=replay, world_path=world_path)
    scenes.push(scene)
    for _ in range(replay.ticks):
        scenes.update(STEP)
    return scene


def test_starts_with_the_room_and_its_neighbour_loaded(ctx: GameContext, world_path: Path):
    scene = play(ctx, world_path, [(1, [])])
    assert scene.room == "West"
    assert set(scene.rooms.loaded) == {"West", "Middle"}
    assert scene.spawn_point == (2 * 16 + 8, 10 * 16)
    assert scene.camera.bounds == scene.rooms.graph.rects["West"]


def test_running_east_enters_the_next_room(ctx: GameContext, world_path: Path):
    entered: list[RoomEntered] = []
    ctx.bus.subscribe(RoomEntered, entered.append)
    scene = play(ctx, world_path, [(5, []), (110, ["right"])])
    assert [(e.room, e.previous) for e in entered] == [("Middle", "West")]
    assert scene.room == "Middle"
    assert set(scene.rooms.loaded) == {"West", "Middle", "East"}
    assert scene.camera.bounds == scene.rooms.graph.rects["Middle"]
    assert scene.camera.gliding
    assert scene.spawn_point == (320 + 2 * 16 + 8, 10 * 16)


def test_hazard_death_respawns_at_the_room_entry_point(ctx: GameContext, world_path: Path):
    died: list[Died] = []
    ctx.bus.subscribe(Died, died.append)
    scene = play(ctx, world_path, [(5, []), (150, ["right"]), (60, [])])
    assert died
    assert scene.room == "Middle"
    assert scene.body.center_x == pytest.approx(scene.spawn_point[0])
    assert scene.body.bottom == scene.spawn_point[1]


def test_draws_and_bakes_rooms_with_the_overlay(
    ctx: GameContext, world_path: Path, display: Display
):
    scene = play(ctx, world_path, [(1, [])])
    scene.show_rooms = True
    for _ in range(30):
        scene.draw(display.canvas, 1.0)
    assert all(layer.baked == layer.total for layer, _ in scene.layers.values())


def test_reload_keeps_the_active_room(ctx: GameContext, world_path: Path):
    scene = play(ctx, world_path, [(5, []), (110, ["right"])])
    old = scene.rooms.loaded["Middle"]
    scene.reload()
    assert scene.room == "Middle"
    assert scene.rooms.loaded["Middle"] is not old
    assert set(scene.layers) == set(scene.rooms.loaded)


def test_reload_survives_a_broken_world(ctx: GameContext, world_path: Path):
    scene = play(ctx, world_path, [(1, [])])
    world_path.write_text("{")
    scene.reload()
    assert set(scene.rooms.loaded) == {"West", "Middle"}
