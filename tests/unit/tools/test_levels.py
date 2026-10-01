from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from tools.levels.__main__ import main
from tools.levels.ldtk import build_project, iid, is_generated
from tools.levels.source import (
    Defs,
    RoomFile,
    Source,
    SourceError,
    check_layout,
    load_source,
    make_room,
    read_toml,
)

from emberwake.engine.core.serde import from_data
from emberwake.engine.world.ldtk import load_project

ROOT = Path(__file__).parents[3]
SCHEMA = json.loads((ROOT / "tools/schemas/ldtk-1.5.3.schema.json").read_text())
DEFS = read_toml(Defs, ROOT / "levels/src/defs.toml")

HALL = """
####################
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#...........b......#
#...........b......#
#.P..a......b..e.e.#
####################
"""
HALL_TOML = """
fields = {}
[entities.a]
type = "Lever"
fields = { Targets = ["b"], Mode = "once" }
[entities.b]
type = "Door"
fields = { Invert = true }
[entities.e]
type = "Ember"
"""
SHAFT = """
####################
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#...k........ppp...#
####################
"""
SHAFT_TOML = """
[entities.k]
type = "Beacon"
[entities.p]
type = "PressurePlate"
fields = { Targets = ["Hall:b"] }
"""


def room_file(text: str) -> RoomFile:
    return from_data(RoomFile, tomllib.loads(text))


def source(**overrides: Any) -> Source:
    rooms = {
        "Hall": ((0, 0), HALL, HALL_TOML),
        "Shaft": ((1, 0), SHAFT, SHAFT_TOML),
    } | overrides
    built = [
        make_room(name, cell, text, room_file(toml)) for name, (cell, text, toml) in rooms.items()
    ]
    check_layout(built)
    return Source(DEFS, built)


def errors(document: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft7Validator(SCHEMA)
    return [error.message for error in validator.iter_errors(document)]


def level(project: dict[str, Any], name: str) -> dict[str, Any]:
    (found,) = [lv for lv in project["levels"] if lv["identifier"] == name]
    return found


def test_generated_project_matches_ldtk_schema():
    assert errors(build_project(source())) == []


def test_validator_catches_missing_required_fields():
    broken = copy.deepcopy(build_project(source()))
    del broken["levels"][0]["layerInstances"][1]["intGridCsv"]
    assert errors(broken)


def test_committed_world_matches_ldtk_schema():
    assert errors(json.loads((ROOT / "levels/world.ldtk").read_text())) == []


def test_committed_world_is_built_from_source():
    committed = json.loads((ROOT / "levels/world.ldtk").read_text())
    rebuilt = build_project(load_source(ROOT / "levels/src"), copy.deepcopy(committed))
    assert rebuilt == committed, "run `uv run python -m tools.levels build --merge`"


def test_loads_through_the_engine_with_fields_and_wiring(tmp_path: Path):
    path = tmp_path / "world.ldtk"
    path.write_text(json.dumps(build_project(source())))
    project = load_project(path)
    hall, shaft = project.level("Hall"), project.level("Shaft")
    assert hall.field("Generated") is True
    assert (shaft.world_x, shaft.world_y) == (320, 0)
    assert [(n.dir, n.level_iid) for n in hall.neighbours] == [("e", shaft.iid)]

    (lever,) = hall.entities("Lever")
    (door,) = hall.entities("Door")
    assert lever.field("Mode") == "once"
    assert [ref["entityIid"] for ref in lever.field("Targets")] == [door.iid]
    assert (door.px, door.width, door.height) == ((12 * 16, 7 * 16), 16, 48)
    assert door.field("Invert") is True
    assert door.field("Mode") == "any"
    assert [ember.field("Value") for ember in hall.entities("Ember")] == [1, 1]
    assert len({ember.iid for ember in hall.entities("Ember")}) == 2
    (start,) = hall.entities("PlayerStart")
    assert start.px == (2 * 16 + 8, 10 * 16)

    (plate,) = shaft.entities("PressurePlate")
    assert plate.width == 48
    (target,) = plate.field("Targets")
    assert (target["entityIid"], target["levelIid"]) == (door.iid, hall.iid)


def test_marker_iids_survive_moving_the_entity():
    moved = HALL.replace("#.P..a", "#.Pa..")
    before = build_project(source())
    after = build_project(source(Hall=((0, 0), moved, HALL_TOML)))
    lever_iid = iid("entity:Hall:a")
    assert lever_iid in json.dumps(before)
    assert lever_iid in json.dumps(after)


def test_merge_keeps_hand_made_levels_defs_and_uids():
    first = build_project(source())
    hand = copy.deepcopy(level(first, "Shaft"))
    hand |= {"identifier": "Cave", "iid": "cave", "uid": 999, "worldY": 176, "fieldInstances": []}
    first["levels"].append(hand)
    first["defs"]["entities"].append({**first["defs"]["entities"][0], "identifier": "Sign"})
    uids = {lv["identifier"]: lv["uid"] for lv in first["levels"]}

    merged = build_project(source(), copy.deepcopy(first))
    assert [lv["identifier"] for lv in merged["levels"]] == ["Hall", "Shaft", "Cave"]
    assert {lv["identifier"]: lv["uid"] for lv in merged["levels"]} == uids
    assert not is_generated(level(merged, "Cave"))
    assert "Sign" in [d["identifier"] for d in merged["defs"]["entities"]]
    cave_neighbours = level(merged, "Cave")["__neighbours"]
    assert cave_neighbours == [{"dir": "n", "levelIid": level(merged, "Shaft")["iid"]}]
    assert merged["nextUid"] > max(uids.values())

    only_hall = build_project(Source(DEFS, source().rooms[:1]), merged)
    assert [lv["identifier"] for lv in only_hall["levels"]] == ["Hall", "Cave"]


def test_merge_refuses_to_replace_a_hand_made_level():
    first = build_project(source())
    level(first, "Hall")["fieldInstances"] = []
    with pytest.raises(SourceError, match="hand-made levels"):
        build_project(source(), first)


ROOM = HALL.replace("#.P..a", "#.P...").replace("b", ".").replace("e", ".")
"""A bare room with only a PlayerStart at (2, 9)."""


def put(text: str, x: int, y: int, chars: str) -> str:
    rows = text.strip().splitlines()
    rows[y] = rows[y][:x] + chars + rows[y][x + len(chars) :]
    return "\n".join(rows)


@pytest.mark.parametrize(
    ("text", "toml", "message"),
    [
        (put(ROOM, 3, 9, "x"), '[entities.x]\ntype = "Statue"', "unknown entity type"),
        (put(ROOM, 3, 9, "xx"), '[entities.x]\ntype = "Lever"', "must be"),
        (
            put(ROOM, 3, 9, "x"),
            '[entities.x]\ntype = "Lever"\nfields = { Colour = 1 }',
            "no fields",
        ),
        (
            put(ROOM, 3, 9, "x"),
            '[entities.x]\ntype = "Lever"\nfields = { Mode = 3 }',
            "expected String",
        ),
        (
            put(ROOM, 3, 9, "x"),
            '[entities.x]\ntype = "Ember"\nfields = { Value = true }',
            "expected Int",
        ),
        (
            put(ROOM, 3, 9, "x"),
            '[entities.x]\ntype = "Lever"\nfields = { Targets = "y" }',
            "must be a list",
        ),
        (
            put(ROOM, 3, 9, "x"),
            '[entities.x]\ntype = "Lever"\nfields = { Targets = [1] }',
            "marker strings",
        ),
        (
            put(ROOM, 3, 9, "x"),
            '[entities.x]\ntype = "Lever"\nfields = { Targets = ["Nowhere:y"] }',
            "not a single entity marker",
        ),
        (ROOM, "fields = { Backdrop = 'x' }", "unknown level fields"),
    ],
)
def test_compile_errors(text: str, toml: str, message: str):
    with pytest.raises(SourceError, match=message):
        build_project(Source(DEFS, [make_room("Bad", (0, 0), text, room_file(toml))]))


def test_max_count_per_level():
    defs = copy.deepcopy(DEFS)
    defs.entities["PlayerStart"].max_count = 1
    with pytest.raises(SourceError, match="more than 1 PlayerStart"):
        build_project(Source(defs, [make_room("Bad", (0, 0), put(ROOM, 5, 9, "P"))]))


def test_ambiguous_ref_is_an_error():
    toml = HALL_TOML.replace('Targets = ["b"]', 'Targets = ["e"]')
    with pytest.raises(SourceError, match="not a single entity marker"):
        build_project(source(Hall=((0, 0), HALL, toml)))


def write_source(directory: Path) -> None:
    directory.mkdir()
    (directory / "defs.toml").write_text((ROOT / "levels/src/defs.toml").read_text())
    (directory / "world.toml").write_text("[rooms.Hall]\ncell = [0, 0]\n")
    (directory / "hall.txt").write_text(HALL)
    (directory / "hall.toml").write_text(HALL_TOML)


def test_cli_refuses_to_overwrite_without_merge(tmp_path: Path):
    src, out = tmp_path / "src", tmp_path / "world.ldtk"
    write_source(src)
    args = ["build", "--src", str(src), "--out", str(out)]
    assert main(args) == 0
    assert main(args) == 1
    assert main([*args, "--merge"]) == 0
    assert main([*args, "--force"]) == 0
    assert load_project(out).level("Hall").entities("Lever")


def test_cli_reports_source_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    src = tmp_path / "src"
    write_source(src)
    (src / "hall.toml").write_text("[entities.a]\ntype = 3\n")
    assert main(["build", "--src", str(src), "--out", str(tmp_path / "w.ldtk")]) == 1
    assert "hall.toml" in capsys.readouterr().err
