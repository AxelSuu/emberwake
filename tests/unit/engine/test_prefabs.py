from __future__ import annotations

import doctest
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from emberwake.engine.core.serde import SerdeError
from emberwake.engine.ecs import Registry
from emberwake.engine.ecs import prefabs as prefabs_module
from emberwake.engine.ecs.prefabs import Prefab, build, check, load_prefabs

if TYPE_CHECKING:
    from pathlib import Path

REGISTRY = Registry()


@REGISTRY.register
@dataclass(slots=True)
class Wired:
    targets: list[str] = field(default_factory=list)
    mode: str = "toggle"


@REGISTRY.register
@dataclass(slots=True)
class Tagged:
    pass


LEVER = Prefab(
    components={"Wired": {"mode": "once"}, "Tagged": {}},
    fields={"Targets": "Wired.targets", "Mode": "Wired.mode"},
    persist=["Wired"],
)


def test_docstring_example():
    assert doctest.testmod(prefabs_module).failed == 0


def test_build_maps_fields_over_prefab_values():
    built = build(LEVER, {"Targets": ["door"], "Extra": 3}, REGISTRY)
    assert built == {"Wired": Wired(["door"], "once"), "Tagged": Tagged()}
    assert build(LEVER, {"Mode": None}, REGISTRY)["Wired"] == Wired([], "once")
    assert LEVER.components["Wired"] == {"mode": "once"}


def test_build_errors():
    with pytest.raises(KeyError, match="unknown component"):
        build(Prefab(components={"Nope": {}}), {}, REGISTRY)
    with pytest.raises(SerdeError, match="targets"):
        build(LEVER, {"Targets": "door"}, REGISTRY)


def test_check_finds_bad_names_and_mappings():
    assert check(LEVER, REGISTRY) == []
    bad = Prefab(
        components={"Wired": {}, "Ghost": {}},
        fields={"A": "Nope.x", "B": "Wired.colour", "C": "Tagged.x"},
        persist=["Tagged", "Phantom"],
    )
    assert check(bad, REGISTRY) == [
        "unknown component 'Ghost'",
        "unknown component 'Phantom'",
        "A maps to unknown component 'Nope'",
        "B maps to missing field 'Wired.colour'",
        "C maps to missing field 'Tagged.x'",
        "persists Tagged, which the prefab does not have",
    ]
    assert check(Prefab(fields={"T": "Tagged"}), REGISTRY) == ["T maps to missing field 'Tagged'"]


def test_load_prefabs(tmp_path: Path):
    path = tmp_path / "prefabs.toml"
    path.write_text('[marker]\n[lever]\ncomponents = { Wired = { mode = "once" } }\n')
    assert load_prefabs(path) == {
        "marker": Prefab(),
        "lever": Prefab(components={"Wired": {"mode": "once"}}),
    }
