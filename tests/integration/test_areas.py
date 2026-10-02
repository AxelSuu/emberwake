"""Areas in play: light % from the whole world, and the grade following the active area's."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, MarkerSpec, RoomFile, Source, make_room, read_toml

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.render.post import Grade
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.ldtk import load_project
from emberwake.engine.world.spawning import WorldState
from emberwake.game import paths
from emberwake.game.actions import Action
from emberwake.game.areas import AreaLight
from emberwake.game.data.save import SaveSlot, save_slot
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.game.context import GameContext

STEP = 1 / 60
WALL, OPEN = "#" * 20, "." * 20
TO_EAST = [(5, []), (260, ["right"])]
"""From West's start into East, two rooms on."""


def room(markers: str, *, left: bool = False, right: bool = False) -> str:
    row = ("#" if left else ".") + markers.ljust(18, ".") + ("#" if right else ".")
    side = ("#" if left else ".") + "." * 18 + ("#" if right else ".")
    return "\n".join([WALL, *[side] * 8, row, WALL])


@pytest.fixture
def world_path(tmp_path: Path) -> Path:
    defs = read_toml(Defs, paths.levels("src/defs.toml"))
    beacon = {"k": MarkerSpec("Beacon")}
    rooms = [
        make_room("West", (0, 0), room(".Pk", left=True), RoomFile({"Area": "lab"}, beacon)),
        make_room("Middle", (1, 0), room(""), RoomFile({"Area": "lab"})),
        make_room("East", (2, 0), room("..P..k"), RoomFile({}, beacon)),
        make_room("Far", (3, 0), room("..k", right=True), RoomFile({}, beacon)),
    ]
    path = tmp_path / "world.ldtk"
    path.write_text(json.dumps(build_project(Source(defs, rooms))))
    return path


def start(ctx: GameContext, world_path: Path, room: str | None = "West") -> GameplayScene:
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room, world_path=world_path)
    scenes.push(scene)
    scenes.apply_pending()
    return scene


def drive(scene: GameplayScene, runs: list[tuple[int, list[str]]]) -> None:
    replay = Replay(scene.room, 0, runs)
    scene.replay = ReplayPlayer(replay, Action)
    for _ in range(replay.ticks):
        scene.manager.update(STEP)


def beacon_of(world_path: Path, room: str) -> str:
    level = load_project(world_path).level(room)
    (beacon,) = level.entities("Beacon")
    return beacon.iid


def test_light_counts_unloaded_rooms_from_the_saved_world(ctx: GameContext, world_path: Path):
    far = beacon_of(world_path, "Far")
    world = WorldState({far: {"Beacon": {"lit": True}}})
    save_slot(ctx.storage, ctx.slot, SaveSlot(room="West", world=world))
    scene = start(ctx, world_path, room=None)
    assert "Far" not in scene.rooms.loaded
    assert scene.light == {"lab": AreaLight(0, 1), "quarter": AreaLight(1, 2)}
    assert scene.area == "lab"
    assert scene.area_grade.light == 0.0


def test_relighting_a_beacon_brings_the_colour_back(ctx: GameContext, world_path: Path):
    scene = start(ctx, world_path)
    grade = Grade(saturation=0.9)
    assert scene.area_grade.apply(grade).saturation == pytest.approx(0.9 * scene.areas.dim)
    drive(scene, [(5, []), (2, ["interact"]), (5, [])])
    assert scene.light["lab"] == AreaLight(1, 1)
    assert 0.0 < scene.area_grade.light < 1.0
    drive(scene, [(150, [])])
    assert scene.area_grade.apply(grade) == grade


def test_crossing_into_another_area_aims_at_its_light(ctx: GameContext, world_path: Path):
    scene = start(ctx, world_path)
    drive(scene, [(5, []), (2, ["interact"]), (130, [])])
    assert scene.area_grade.light == 1.0
    drive(scene, TO_EAST)
    assert (scene.room, scene.area) == ("East", "quarter")
    assert scene.area_grade.target == 0.0
    assert scene.area_grade.light < 1.0


def test_the_scene_exposes_the_rooms_music_with_the_areas_as_fallback(
    ctx: GameContext, world_path: Path
):
    scene = start(ctx, world_path)
    assert scene.music == ""
    drive(scene, TO_EAST)
    assert (scene.room, scene.music) == ("East", "quarter")
