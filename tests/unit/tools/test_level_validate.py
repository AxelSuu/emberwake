from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from tools.levels.__main__ import main
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml
from tools.levels.validate import validate

from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import Registry
from emberwake.engine.ecs.prefabs import Prefab, load_prefabs
from emberwake.engine.world.ldtk import Project, load_project

ROOT = Path(__file__).parents[3]
DEFS = read_toml(Defs, ROOT / "levels/src/defs.toml")
REGISTRY = Registry()


@REGISTRY.register
@dataclass(slots=True)
class Wired:
    targets: list[str] = field(default_factory=list)


@REGISTRY.register
@dataclass(slots=True)
class Value:
    amount: int = 1


WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
ROOM = "\n".join([WALL, *[INSIDE] * 8, "#.Pa.b.e.e" + "." * 9 + "#", WALL])
TOML = """
[entities.a]
type = "Lever"
fields = { Targets = ["b"] }
[entities.b]
type = "Beacon"
[entities.e]
type = "Ember"
fields = { Value = 3 }
"""
GOOD = {
    "player_start": Prefab(),
    "lever": Prefab(components={"Wired": {}}, fields={"Targets": "Wired.targets"}),
    "beacon": Prefab(),
    "ember": Prefab(components={"Value": {}}, fields={"Value": "Value.amount"}),
}


def project() -> Project:
    room = make_room("Hall", (0, 0), ROOM, from_data(RoomFile, tomllib.loads(TOML)))
    return from_data(Project, build_project(Source(DEFS, [room])))


def test_committed_world_matches_the_prefabs_and_backdrops():
    world = load_project(ROOT / "levels/world.ldtk")
    prefabs = load_prefabs(ROOT / "content/prefabs.toml")
    backdrops = tomllib.loads((ROOT / "content/backdrops.toml").read_text())
    assert validate(world, prefabs, backdrops=backdrops) == []


def test_unknown_backdrops():
    problems = validate(project(), GOOD, REGISTRY, backdrops={"ruins"})
    assert problems == ["Hall: no backdrop [cavern]"]


def test_a_matching_project_has_no_problems():
    assert validate(project(), GOOD, REGISTRY) == []


@pytest.mark.parametrize(
    ("prefabs", "message"),
    [
        ({**GOOD, "ember": None}, "Ember: no prefab [ember]"),
        ({**GOOD, "lever": Prefab(components={"Wired": {}}, fields={"Wires": "Wired.targets"})},
         "no LDtk fields ['Wires'] for prefab lever"),
        ({**GOOD, "ember": Prefab(components={"Wired": {}}, fields={"Value": "Wired.targets"})},
         "expected list, got int"),
        ({**GOOD, "beacon": Prefab(components={"Glow": {}})}, "prefab beacon: unknown component"),
    ],
)  # fmt: skip
def test_problems(prefabs: dict[str, Prefab | None], message: str):
    present = {name: p for name, p in prefabs.items() if p is not None}
    problems = validate(project(), present, REGISTRY)
    assert any(message in problem for problem in problems), problems
    if "no prefab" in message:
        assert len(problems) == 1


def conditioned(entity: str, fields: dict[str, str]) -> list[str]:
    room_file = from_data(RoomFile, {"entities": {"e": {"type": entity, "fields": fields}}})
    rows = [WALL, *[INSIDE] * 8, "#.P.e" + "." * 14 + "#", WALL]
    room = make_room("Hall", (0, 0), "\n".join(rows), room_file)
    world = from_data(Project, build_project(Source(DEFS, [room])))
    return validate(world, {**GOOD, "flag_switch": Prefab()}, REGISTRY)


@pytest.mark.parametrize(
    ("entity", "fields", "message"),
    [
        ("Ember", {"Requires": "met >"}, "Requires 'met >' is not a condition"),
        ("Ember", {"Unless": "two words"}, "Unless 'two words' is not a condition"),
        ("FlagSwitch", {"Condition": "has.shard=>3"}, "Condition 'has.shard=>3' is not"),
    ],
)
def test_malformed_conditions(entity: str, fields: dict[str, str], message: str):
    problems = conditioned(entity, fields)
    assert any(message in problem for problem in problems), problems


def test_well_formed_conditions_pass():
    fields = {"Requires": "has.shard>=3", "Unless": "!met"}
    assert conditioned("Ember", fields) == []


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["validate"]) == 0
    bare = "\n".join([WALL, *[INSIDE] * 8, "#.P" + "." * 16 + "#", WALL])
    world = tmp_path / "world.ldtk"
    world.write_text(json.dumps(build_project(Source(DEFS, [make_room("Hall", (0, 0), bare)]))))
    prefabs = tmp_path / "prefabs.toml"
    prefabs.write_text("[beacon]\n")
    assert main(["validate", "--world", str(world), "--prefabs", str(prefabs)]) == 1
    assert "no prefab [player_start]" in capsys.readouterr().err
