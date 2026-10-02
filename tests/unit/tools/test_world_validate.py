from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
from tools.levels.checks import check_world
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml
from tools.levels.world import Rules, load_rules

from emberwake.engine.core.dialogue import Node
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.world.ldtk import Project, load_project
from emberwake.game.grants import GrantSpec

ROOT = Path(__file__).parents[3]
DEFS = read_toml(Defs, ROOT / "levels/src/defs.toml")
PREFABS = load_prefabs(ROOT / "content/prefabs.toml")
GRANTS = {
    "dash": GrantSpec("ability"),
    "flare": GrantSpec("ability"),
    "shard": GrantSpec("item", max=12),
}
DOOR = "#" + "." * 8 + "#" + "." * 9
ROW = "." * 20


def hall(rows: dict[int, str] | None = None) -> str:
    """A 20x11 room open to both sides at rows 5 to 8, with `rows` swapped in."""
    lines = ["#" * 20, *["#" + "." * 18 + "#"] * 4, *[ROW] * 4, *["#" * 20] * 2]
    for row, text in (rows or {}).items():
        lines[row] = text.ljust(20, ".")
    return "\n".join(lines)


def world(rooms: dict[str, tuple[tuple[int, int], str, str]]) -> Project:
    made = [
        make_room(name, cell, text, from_data(RoomFile, tomllib.loads(toml)))
        for name, (cell, text, toml) in rooms.items()
    ]
    return from_data(Project, build_project(Source(DEFS, made)))


def problems(
    rooms: dict[str, tuple[tuple[int, int], str, str]], entrances: bool = False, **rules: Any
) -> list[str]:
    """Problems of the rooms, leaving out missing PlayerStarts unless `entrances`."""
    rules = {"start": "A", "abilities": (), "grants": GRANTS} | rules
    found = check_world(world(rooms), PREFABS, Rules(**rules))
    return [line for line in found if entrances or "PlayerStart within" not in line]


def pair(left: str = "", right: str = "", a: str = "", b: str = "") -> dict[str, Any]:
    """Two side-by-side halls with a PlayerStart in the first."""
    return {
        "A": ((0, 0), hall({8: "..P" + a}), left),
        "B": ((1, 0), hall({8: "..P" + b}), right),
    }


def reaching(found: list[str]) -> list[str]:
    return [line for line in found if "not reachable" in line]


def test_the_committed_world_passes():
    project = load_project(ROOT / "levels/world.ldtk")
    assert check_world(project, PREFABS, load_rules(ROOT / "content")) == []


def test_a_target_that_does_not_exist():
    toml = '[entities.l]\ntype = "Lever"\n'
    project = world({"A": ((0, 0), hall({8: "..P..l"}), toml)})
    lever = project.level("A").entities("Lever")[0]
    lever.field_instances[0].value = [{"entityIid": "nowhere"}]
    found = check_world(project, PREFABS, Rules(start="A", grants=GRANTS))
    assert found == [f"A Lever {lever.iid}: targets nowhere, which does not exist"]


class TestEntrances:
    def test_each_side_of_an_opening_needs_a_player_start_near_it(self):
        rooms = pair()
        rooms["A"] = ((0, 0), hall({8: "P"}), "")
        rooms["B"] = ((1, 0), hall({8: ROW[:15] + "P"}), "")
        found = problems(rooms, entrances=True)
        assert [line.split(" has")[0] for line in found] == [
            "A: the way to B at tile (19, 5)",
            "B: the way to A at tile (0, 5)",
        ]

    def test_a_player_start_close_by_is_enough(self):
        rooms = pair()
        rooms["A"] = ((0, 0), hall({8: ROW[:17] + "P"}), "")
        assert problems(rooms, entrances=True) == []

    def test_lab_rooms_are_skipped(self):
        rooms = pair(left='fields = { Area = "lab" }')
        rooms["B"] = ((1, 0), hall({8: ROW[:10] + "P"}), "")
        assert problems(rooms, entrances=True) == [
            "B: the way to A at tile (0, 5) has no PlayerStart within 6 tiles"
        ]

    def test_a_crack_too_low_for_the_player_is_no_entrance(self):
        wall = {5: "#" * 20, 6: "#" * 20, 7: "#" * 20}
        rooms = pair()
        rooms["A"] = ((0, 0), hall(wall | {8: "P" + "#" * 18}), "")
        rooms["B"] = ((1, 0), hall(wall | {8: ROW[:18] + "P"}), "")
        assert [x for x in problems(rooms, entrances=True) if "PlayerStart" in x] == []


class TestFlags:
    def test_a_flag_nothing_sets(self):
        found = problems(
            pair('[entities.e]\ntype = "Ember"\nfields = { Requires = "seen" }', a="e")
        )
        assert [line.split(": ")[1] for line in found] == [
            "Requires reads seen, which nothing sets"
        ]

    def test_a_set_flag_a_dialogue_and_the_shop_set_flags(self):
        left = """
[entities.z]
type = "SetFlag"
fields = { Flag = "a_flag" }
[entities.e]
type = "Ember"
fields = { Requires = "a_flag" }
[entities.f]
type = "Ember"
fields = { Requires = "talked" }
[entities.g]
type = "Ember"
fields = { Unless = "up_hp>=2" }
"""
        talk = {"talk": {"start": Node(set={"talked": 1})}}
        found = problems(pair(left, a="zefg"), dialogues=talk, shop_flags={"up_hp"})
        assert [line for line in found if "Ember" in line] == []

    def test_a_flag_the_game_sets_itself_is_known(self):
        found = problems(
            pair('[entities.e]\ntype = "Ember"\nfields = { Requires = "boss_dead" }', a="e"),
            code_flags={"boss_dead"},
        )
        assert found == []

    def test_a_condition_on_a_flag_switch(self):
        left = '[entities.s]\ntype = "FlagSwitch"\nfields = { Condition = "!lit" }'
        found = problems(pair(left, a="s"))
        assert [line.split(": ")[1] for line in found] == [
            "Condition reads lit, which nothing sets"
        ]

    @pytest.mark.parametrize(
        ("thing", "message"),
        [
            ("rope", "Requires reads has.rope, not in grants.toml"),
            ("flare", "Requires reads has.flare, which nothing gives"),
        ],
    )
    def test_has_needs_a_thing_that_exists_and_is_given(self, thing: str, message: str):
        left = f'[entities.e]\ntype = "Ember"\nfields = {{ Requires = "has.{thing}" }}'
        assert [x.split(": ")[1] for x in problems(pair(left, a="e"))] == [message]

    def test_has_is_met_by_a_pickup_a_dialogue_or_the_start(self):
        left = """
[entities.g]
type = "Grant"
fields = { Thing = "flare" }
[entities.e]
type = "Ember"
fields = { Requires = "has.flare" }
[entities.f]
type = "Ember"
fields = { Requires = "has.dash>=1" }
"""
        assert problems(pair(left, a="gef"), abilities=("dash",)) == []
        talk = {"talk": {"start": Node(action="give:flare")}}
        ember = '[entities.e]\ntype = "Ember"\nfields = { Requires = "has.flare" }'
        assert problems(pair(ember, a="e"), dialogues=talk) == []

    def test_a_grant_of_an_unknown_thing(self):
        found = problems(pair('[entities.g]\ntype = "Grant"\nfields = { Thing = "rope" }', a="g"))
        assert [line.split(": ")[1] for line in found] == ["Thing 'rope' is not granted"]


LEVER_AND_DOOR = """
[entities.d]
type = "Door"
[entities.l]
type = "Lever"
fields = { Targets = ["d"] }
"""


def partition(floor: str) -> str:
    """A hall split at column 10 by a 3 tall door `d`; `floor` is its bottom row."""
    rows = dict.fromkeys(range(1, 6), "#" * 10 + "#" + "." * 9)
    rows |= dict.fromkeys(range(6, 9), "." * 10 + "d" + "." * 9)
    floor = floor.ljust(20, ".")
    return hall(rows | {8: floor[:10] + "d" + floor[11:]})


def walled(lever_column: int) -> dict[str, Any]:
    """Two halls, the first split by a door with a lever at `lever_column`."""
    rooms = pair()
    floor = "..P" + "." * 17
    rooms["A"] = (
        (0, 0),
        partition(floor[:lever_column] + "l" + floor[lever_column + 1 :]),
        LEVER_AND_DOOR,
    )
    return rooms


class TestReachability:
    def test_a_room_nothing_opens_to(self):
        rooms = pair()
        rooms["B"] = ((3, 0), rooms["B"][1], "")
        assert reaching(problems(rooms)) == ["B: not reachable from A, it has no open way in"]

    def test_a_connected_world_is_reachable(self):
        assert reaching(problems(pair())) == []

    def test_a_door_with_its_lever_out_of_reach(self):
        found = reaching(problems(walled(15)))
        assert len(found) == 1
        assert found[0].startswith("B: not reachable from A, it is behind Door")
        assert "in A" in found[0]

    def test_a_door_whose_lever_can_be_pulled(self):
        assert reaching(problems(walled(5))) == []

    def test_an_inverted_door_is_open(self):
        rooms = walled(15)
        toml = LEVER_AND_DOOR.replace('type = "Door"', 'type = "Door"\nfields = { Invert = true }')
        rooms["A"] = (rooms["A"][0], rooms["A"][1], toml)
        assert reaching(problems(rooms)) == []

    def test_a_flag_switch_opens_a_door_once_the_flag_is_set(self):
        toml = """
[entities.d]
type = "Door"
[entities.s]
type = "FlagSwitch"
fields = { Condition = "lit", Targets = ["d"] }
[entities.z]
type = "SetFlag"
fields = { Flag = "lit" }
"""
        rooms = pair()
        rooms["A"] = ((0, 0), partition("..Pz.s....d"), toml)
        assert reaching(problems(rooms)) == []
        rooms["A"] = ((0, 0), partition("..P..s....d....z"), toml)
        assert len(reaching(problems(rooms))) == 1

    def test_an_all_door_needs_every_source(self):
        toml = LEVER_AND_DOOR.replace('type = "Door"', 'type = "Door"\nfields = { Mode = "all" }')
        toml += '[entities.m]\ntype = "Lever"\nfields = { Targets = ["d"] }\n'
        rooms = pair()
        rooms["A"] = ((0, 0), partition("..P.l.m...d"), toml)
        assert reaching(problems(rooms)) == []
        rooms["A"] = ((0, 0), partition("..P.l.....d....m"), toml)
        assert len(reaching(problems(rooms))) == 1


def gapped(grant_at: str = "", grant: str = "dash") -> dict[str, Any]:
    """A hall with an 8 tile pit; `grant_at` places a Grant of dash in it."""
    floor = {9: "#" * 6 + "." * 8 + "#" * 6, 10: "#" * 6 + "." * 8 + "#" * 6}
    toml = f'[entities.g]\ntype = "Grant"\nfields = {{ Thing = "{grant}" }}\n'
    rows = floor | {8: "..P" + grant_at}
    rooms = pair()
    rooms["A"] = ((0, 0), hall(rows), toml if grant_at else "")
    return rooms


class TestAbilities:
    def test_a_gap_only_the_dash_crosses(self):
        found = reaching(problems(gapped()))
        assert found == ["B: not reachable from A, it needs dash, granted in nowhere"]

    def test_the_dash_crosses_it(self):
        assert reaching(problems(gapped(), abilities=("dash",))) == []

    def test_a_grant_before_the_gap_is_enough(self):
        assert reaching(problems(gapped(".g"))) == []

    def test_a_grant_beyond_the_gap_is_a_later_ability(self):
        rooms = gapped()
        rooms["B"] = (
            (1, 0),
            hall({8: "..P.g"}),
            '[entities.g]\ntype = "Grant"\nfields = { Thing = "dash" }',
        )
        found = reaching(problems(rooms))
        assert found == ["B: not reachable from A, it needs dash, granted in B"]

    def test_an_npc_who_gives_the_ability_counts(self):
        rooms = gapped()
        rooms["A"] = (
            (0, 0),
            rooms["A"][1].replace("..P.", "..Pt", 1),
            '[entities.t]\ntype = "Tinker"',
        )
        talk = {"tinker": {"start": Node(action="give:dash")}}
        assert reaching(problems(rooms, dialogues=talk)) == []

    def test_a_start_in_the_lab_or_missing_checks_nothing(self):
        rooms = pair()
        rooms["B"] = ((3, 0), rooms["B"][1], "")
        assert reaching(problems(rooms, start="Wake")) == []
        rooms["A"] = (rooms["A"][0], rooms["A"][1], 'fields = { Area = "lab" }')
        assert reaching(problems(rooms)) == []

    def test_lab_and_trial_rooms_need_no_way_in(self):
        rooms = pair()
        rooms["B"] = ((3, 0), rooms["B"][1], 'fields = { Area = "lab" }')
        rooms["C"] = ((5, 0), hall({8: "..P"}), "")
        assert reaching(problems(rooms, trials={"C"})) == []

    def test_a_start_room_without_a_player_start(self):
        rooms = pair()
        rooms["A"] = ((0, 0), hall(), "")
        assert "A: the start room has no PlayerStart" in problems(rooms)


ARENA = """
[entities.d]
type = "Door"
[entities.z]
type = "Encounter"
fields = { Doors = ["d"] }
[entities.w]
type = "WaveSpawn"
fields = { Encounter = "z", Wave = 1, Kind = "clockrat" }
"""


def arena(toml: str = ARENA, floor: str = "..Pzw") -> dict[str, Any]:
    rooms = pair()
    rooms["A"] = ((0, 0), partition(floor), toml)
    return rooms


class TestEncounters:
    def test_a_door_an_encounter_shuts_does_not_wall_off_the_rest(self):
        assert problems(arena()) == []

    def test_a_door_nothing_opens_still_does(self):
        toml = ARENA.replace('fields = { Doors = ["d"] }', "")
        assert len(reaching(problems(arena(toml)))) == 1

    def test_an_unknown_kind(self):
        found = problems(arena(ARENA.replace('"clockrat"', '"dragon"')))
        assert [line.split(": ")[1][:23] for line in found] == ["Kind 'dragon' is not an"]

    def test_waves_must_count_up_from_one(self):
        found = problems(arena(ARENA.replace("Wave = 1", "Wave = 2")))
        assert [line.split(": ")[1] for line in found] == ["waves [2] do not run from 1 up"]

    def test_an_encounter_without_waves(self):
        toml = ARENA.split("[entities.w]", maxsplit=1)[0]
        found = problems(arena(toml, floor="..Pz"))
        assert [line.split(": ")[1] for line in found] == ["waves [] do not run from 1 up"]

    def test_a_wave_spawn_must_name_an_encounter(self):
        found = problems(arena(ARENA.replace('Encounter = "z"', 'Encounter = "d"')))
        assert [line.split(": ")[1] for line in found] == [
            "Encounter is Door, not an Encounter",
            "waves [] do not run from 1 up",
        ]

    def test_a_wave_spawn_in_another_room_than_its_encounter(self):
        rooms = arena()
        toml = '[entities.s]\ntype = "WaveSpawn"\nfields = { Encounter = "A:z", Kind = "gearbug" }'
        rooms["B"] = ((1, 0), hall({8: "..Ps"}), toml)
        found = problems(rooms)
        assert [line.split(": ")[1] for line in found] == ["Encounter is in A, not in this room"]

    def test_doors_must_be_doors(self):
        found = problems(arena(ARENA.replace('Doors = ["d"]', 'Doors = ["w"]')))
        assert [line.split(": ")[1] for line in found if "Doors" in line] == [
            f"Doors names {_iid(found)}, which is a WaveSpawn, not a Door"
        ]


def _iid(found: list[str]) -> str:
    return next(line.split("Doors names ")[1].split(",")[0] for line in found if "Doors" in line)
