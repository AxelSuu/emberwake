from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from tools.levels.ldtk import build_project
from tools.levels.source import (
    Defs,
    EntitySpec,
    FieldSpec,
    MarkerSpec,
    RoomFile,
    Source,
    make_room,
    read_toml,
)

import emberwake.game.components  # noqa: F401  (registers Beacon)
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import COMPONENTS, Registry
from emberwake.engine.ecs.prefabs import Prefab
from emberwake.engine.render.post import Grade
from emberwake.engine.world.ldtk import Level, Project
from emberwake.engine.world.spawning import WorldState
from emberwake.game import paths
from emberwake.game.areas import (
    DEFAULT_AREA,
    AreaGrade,
    AreaLight,
    Areas,
    AreaSpec,
    LightCensus,
    area_of,
    load_areas,
    music_of,
    saturation,
)

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


BEACON = {"beacon": Prefab(components={"Beacon": {}}, persist=["Beacon"])}
RULES = {"beacon": "Beacon.lit"}


def world(*rooms: tuple[str, str, str]) -> list[Level]:
    """Rooms in a row as (name, area, markers): ``k`` a beacon, ``l`` a lamp, ``L`` a lit one."""
    defs = dataclasses.replace(DEFS, entities={**DEFS.entities, "Lamp": LAMP})
    entities = {
        "k": MarkerSpec("Beacon"),
        "l": MarkerSpec("Lamp"),
        "L": MarkerSpec("Lamp", {"Lit": True}),
    }
    built = []
    for column, (name, area, markers) in enumerate(rooms):
        used = {m: spec for m, spec in entities.items() if m in markers}
        row = "#.P" + ".".join(markers) + "." * (16 - max(2 * len(markers) - 1, 0)) + "#"
        text = "\n".join([WALL, *[INSIDE] * 8, row, WALL])
        built.append(make_room(name, (column, 0), text, RoomFile({"Area": area}, used)))
    return from_data(Project, build_project(Source(defs, built))).all_levels


def iids(levels: list[Level], room: str) -> list[str]:
    (level,) = (level for level in levels if level.identifier == room)
    return [entity.iid for entity in level.entities() if entity.identifier != "PlayerStart"]


def lit(*iids: str, component: str = "Beacon") -> WorldState:
    return WorldState({iid: {component: {"lit": True}} for iid in iids})


def test_light_is_lit_beacons_over_beacons_per_area_from_the_world_state():
    levels = world(("Hall", "quarter", "kk"), ("Cellar", "quarter", "k"), ("Lab", "lab", "k"))
    census = LightCensus(levels, BEACON, RULES)
    assert census.count(WorldState()) == {"quarter": AreaLight(0, 3), "lab": AreaLight(0, 1)}
    state = lit(iids(levels, "Hall")[0], *iids(levels, "Cellar"))
    assert census.count(state) == {"quarter": AreaLight(2, 3), "lab": AreaLight(0, 1)}
    assert census.count(state)["quarter"].percent == 66


def test_nothing_to_light_is_fully_lit():
    census = LightCensus(world(("Hall", "quarter", ""), ("Lab", "lab", "k")), BEACON, RULES)
    assert census.count(WorldState())["quarter"] == AreaLight()
    assert (AreaLight().fraction, AreaLight().percent) == (1.0, 100)
    assert (AreaLight(1, 1).percent, AreaLight(1, 3).fraction) == (100, 1 / 3)


@dataclass(slots=True)
class Lamp:
    lit: bool = False


LAMP = EntitySpec("#ffffff", fields={"Lit": FieldSpec("Bool", default=False)})


def test_a_prefab_added_to_the_rules_counts_and_starts_as_placed():
    registry = Registry()
    registry.register(Lamp)
    registry.register(COMPONENTS["Beacon"])
    lamp = Prefab(components={"Lamp": {}}, fields={"Lit": "Lamp.lit"}, persist=["Lamp"])
    levels = world(("Row", "quarter", "lLk"))
    rules = {**RULES, "lamp": "Lamp.lit"}
    census = LightCensus(levels, {**BEACON, "lamp": lamp}, rules, registry)
    assert census.count(WorldState()) == {"quarter": AreaLight(1, 3)}
    unlit, pre_lit, _ = iids(levels, "Row")
    state = lit(unlit, component="Lamp")
    assert census.count(state) == {"quarter": AreaLight(2, 3)}
    state.entities[pre_lit] = {"Lamp": {"lit": False}}
    assert census.count(state) == {"quarter": AreaLight(1, 3)}


def test_a_dark_area_keeps_dim_of_the_saturation_and_a_lit_one_all_of_it():
    assert saturation(0.0, 0.7) == 0.7
    assert saturation(1.0, 0.7) == 1.0
    assert saturation(0.5, 0.6) == 0.8
    grade = Grade((200, 200, 255), (4, 0, 0), saturation=0.9)
    area = AreaGrade(dim=0.5, rate=0.5)
    area.aim(0.0, instantly=True)
    assert area.apply(grade) == Grade((200, 200, 255), (4, 0, 0), saturation=0.45)
    area.aim(1.0)
    area.update(1.0)
    assert area.light == 0.5
    area.update(1.0)
    assert area.apply(grade) == grade
    assert AreaGrade().apply(Grade()).neutral
