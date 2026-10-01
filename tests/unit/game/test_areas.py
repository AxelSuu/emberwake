from __future__ import annotations

from typing import Any

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, Source, make_room, read_toml

from emberwake.engine.core.serde import from_data
from emberwake.engine.world.ldtk import Level, Project
from emberwake.game import paths
from emberwake.game.areas import DEFAULT_AREA, Areas, AreaSpec, area_of, load_areas, music_of

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"


def level(fields: dict[str, Any] | None = None, markers: str = "") -> Level:
    row = "#.P" + markers + "." * (16 - len(markers)) + "#"
    room = make_room("Hall", (0, 0), "\n".join([WALL, *[INSIDE] * 8, row, WALL]))
    room.fields = fields or {}
    (built,) = from_data(Project, build_project(Source(DEFS, [room]))).all_levels
    return built


def test_a_room_without_an_area_is_in_the_quarter():
    assert area_of(level()) == DEFAULT_AREA == "quarter"
    assert area_of(level({"Area": "lab"})) == "lab"


def test_music_is_the_room_s_else_the_area_s():
    areas = Areas(areas={"quarter": AreaSpec(music="streets"), "lab": AreaSpec()})
    assert music_of(level(), areas) == "streets"
    assert music_of(level({"Music": "cistern"}), areas) == "cistern"
    assert music_of(level({"Area": "lab"}), areas) == ""
    assert music_of(level({"Area": "unknown"}), areas) == ""


def test_the_content_loads():
    areas = load_areas(paths.content("areas.toml"))
    assert {"quarter", "lab"} <= areas.areas.keys()
    assert 0 < areas.dim <= 1
