from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from tools.ldtk_scaffold import build_project, main, parse_room

ROOT = Path(__file__).parents[3]
SCHEMA = json.loads((ROOT / "tools/schemas/ldtk-1.5.3.schema.json").read_text())

ROOMS = {
    "Alpha": ["#####", "#P..#", "#=^.#", "#####"],
    "Beta": ["####", "#..#", "####"],
}


def errors(document: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft7Validator(SCHEMA)
    return [error.message for error in validator.iter_errors(document)]


def test_generated_project_matches_ldtk_schema():
    assert errors(build_project(ROOMS)) == []


def test_validator_catches_missing_required_fields():
    broken = copy.deepcopy(build_project(ROOMS))
    del broken["levels"][0]["layerInstances"][1]["intGridCsv"]
    assert errors(broken)


def test_committed_world_matches_ldtk_schema():
    assert errors(json.loads((ROOT / "levels/world.ldtk").read_text())) == []


def test_rooms_are_laid_out_left_to_right_with_neighbours():
    alpha, beta = build_project(ROOMS)["levels"]
    assert (alpha["worldX"], beta["worldX"]) == (0, 320)
    assert alpha["__neighbours"] == [{"dir": "e", "levelIid": beta["iid"]}]


def test_parse_room_rejects_ragged_rows():
    with pytest.raises(ValueError, match="equal length"):
        parse_room("###\n##\n")


def test_refuses_to_overwrite(tmp_path: Path):
    room = tmp_path / "room.txt"
    room.write_text("###\n#P#\n###\n")
    out = tmp_path / "world.ldtk"
    assert main([str(out), str(room)]) == 0
    assert main([str(out), str(room)]) == 1
    assert main([str(out), str(room), "--force"]) == 0
