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
from emberwake.game.areas import Areas, AreaSpec

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


def project(**fields: str) -> Project:
    data = {**tomllib.loads(TOML), "fields": fields}
    room = make_room("Hall", (0, 0), ROOM, from_data(RoomFile, data))
    return from_data(Project, build_project(Source(DEFS, [room])))


AREAS = Areas({"quarter": AreaSpec("quarter"), "lab": AreaSpec()}, {"lever": "Wired.targets"})
NAMES = {"area.quarter.name": "Quarter", "area.lab.name": "Lab"}
PERSISTING = {**GOOD, "lever": Prefab(components={"Wired": {}}, persist=["Wired"])}


def check_areas(world: Project, areas: Areas = AREAS, names: dict[str, str] = NAMES) -> list[str]:
    return validate(world, PERSISTING, REGISTRY, areas=areas, strings=names)


def test_levels_name_known_areas_and_lowercase_music():
    assert check_areas(project(Area="lab", Music="boss_two")) == []
    assert check_areas(project()) == []
    assert check_areas(project(Area="swamp")) == ["Hall: no area [swamp]"]
    assert check_areas(project(Music="Boss Two")) == [
        "Hall: Music 'Boss Two' is not a stem-set name"
    ]


def test_areas_need_names_and_lowercase_music():
    assert check_areas(project(), Areas({"quarter": AreaSpec("Loud")}), {}) == [
        "area quarter: music 'Loud' is not a stem-set name",
        "area quarter: no string area.quarter.name",
    ]


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        ({"ghost": "Wired.targets"}, "light ghost: no prefab [ghost]"),
        ({"ember": "Value.amount"}, "light ember: prefab ember does not persist Value"),
        ({"lever": "Wired.nope"}, "light lever: Wired has no field 'nope'"),
    ],
)
def test_light_rules_must_name_a_persisted_field(rules: dict[str, str], message: str):
    problems = check_areas(project(), Areas({"quarter": AreaSpec()}, rules))
    assert problems == [message]


@REGISTRY.register
@dataclass(slots=True)
class Held:
    beacon: str = ""


LAMPS = """
[entities.b]
type = "Beacon"
[entities.x]
type = "Ember"
[entities.l]
type = "Lamp"
fields = { Beacon = "b" }
[entities.m]
type = "Lamp"
fields = { Beacon = "x" }
[entities.n]
type = "Lamp"
"""
LAMP_PREFABS = {
    **GOOD,
    "lamp": Prefab(components={"Held": {}}, fields={"Beacon": "Held.beacon"}),
}


def lamp_room(toml: str) -> Project:
    rows = [INSIDE] * 6 + ["#.l.m.n" + "." * 12 + "#"] * 2 + ["#.Pbx" + "." * 14 + "#"]
    text = "\n".join([WALL, *rows, WALL])
    room = make_room("Hall", (0, 0), text, from_data(RoomFile, tomllib.loads(toml)))
    return from_data(Project, build_project(Source(DEFS, [room])))


def test_a_lamps_beacon_must_be_a_beacon():
    problems = validate(lamp_room(LAMPS), LAMP_PREFABS, REGISTRY)
    assert len(problems) == 1
    assert "Hall Lamp" in problems[0]
    assert problems[0].endswith("Beacon is Ember, not a Beacon")


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
