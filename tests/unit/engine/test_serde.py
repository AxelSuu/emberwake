from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Literal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from emberwake.engine.core.serde import SerdeError, VersionedCodec, alias, from_data, to_data


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Slot(IntEnum):
    A = 1
    B = 2


@dataclass
class Inner:
    name: str
    tags: list[str] = field(default_factory=list)


@dataclass
class Outer:
    count: int
    ratio: float
    color: Color
    inner: Inner
    maybe: int | None = None
    pair: tuple[int, str] = (0, "")
    many: tuple[float, ...] = ()
    by_slot: dict[Slot, int] = field(default_factory=dict)
    by_id: dict[int, Inner] = field(default_factory=dict)
    mode: Literal["a", "b"] = "a"


SAMPLE = Outer(
    count=3,
    ratio=0.5,
    color=Color.BLUE,
    inner=Inner("x", ["t"]),
    maybe=7,
    pair=(1, "one"),
    many=(1.0, 2.5),
    by_slot={Slot.B: 9},
    by_id={4: Inner("four")},
    mode="b",
)


def test_round_trip():
    assert from_data(Outer, to_data(SAMPLE)) == SAMPLE


def test_to_data_shape():
    data = to_data(SAMPLE)
    assert isinstance(data, dict)
    assert data["color"] == "blue"
    assert data["by_slot"] == {"2": 9}
    assert data["pair"] == [1, "one"]


def test_missing_fields_use_defaults_and_unknown_keys_are_ignored():
    data = {"count": 1, "ratio": 1, "color": "red", "inner": {"name": "n"}, "extra": True}
    assert from_data(Outer, data) == Outer(1, 1.0, Color.RED, Inner("n"))


@pytest.mark.parametrize(
    ("data", "path"),
    [
        ({"ratio": 1.0, "color": "red", "inner": {"name": "n"}}, "$.count"),
        ({"count": True, "ratio": 1.0, "color": "red", "inner": {"name": "n"}}, "$.count"),
        ({"count": 1, "ratio": "x", "color": "red", "inner": {"name": "n"}}, "$.ratio"),
        ({"count": 1, "ratio": 1.0, "color": "green", "inner": {"name": "n"}}, "$.color"),
        ({"count": 1, "ratio": 1.0, "color": "red", "inner": {"name": 5}}, "$.inner.name"),
        (
            {"count": 1, "ratio": 1.0, "color": "red", "inner": {"name": "n", "tags": [1]}},
            "$.inner.tags[0]",
        ),
        ({"count": 1, "ratio": 1.0, "color": "red", "inner": {"name": "n"}, "mode": "c"}, "$.mode"),
        (
            {"count": 1, "ratio": 1.0, "color": "red", "inner": {"name": "n"}, "pair": [1]},
            "$.pair",
        ),
    ],
)
def test_errors_report_path(data: dict[str, Any], path: str):
    with pytest.raises(SerdeError) as info:
        from_data(Outer, data)
    assert info.value.path == path


@given(st.integers(), st.floats(allow_nan=False), st.text(), st.lists(st.text()))
def test_round_trip_property(count: int, ratio: float, name: str, tags: list[str]):
    obj = Outer(count, ratio, Color.RED, Inner(name, tags))
    assert from_data(Outer, to_data(obj)) == obj


@dataclass
class V2:
    full_name: str
    level: int = 1


CODEC = VersionedCodec(
    V2,
    version=2,
    migrations={1: lambda d: {"full_name": d["name"]}},
)


def test_codec_migrates_old_versions():
    assert CODEC.load({"version": 1, "data": {"name": "ada"}}) == V2("ada")


def test_codec_round_trip():
    assert CODEC.load(CODEC.dump(V2("x", 3))) == V2("x", 3)


@pytest.mark.parametrize(
    "raw",
    [None, {}, {"version": "1"}, {"version": 3, "data": {}}, {"version": 2, "data": []}],
)
def test_codec_rejects_bad_envelopes(raw: object):
    with pytest.raises(SerdeError):
        CODEC.load(raw)


def test_codec_requires_every_migration_step():
    codec = VersionedCodec(V2, version=3, migrations={2: lambda d: d})
    with pytest.raises(SerdeError, match="no migration from version 1"):
        codec.load({"version": 1, "data": {"full_name": "x"}})


@dataclass
class External:
    identifier: str = alias("__identifier")
    world_x: int = alias("worldX", default=0)


def test_alias_keys():
    assert from_data(External, {"__identifier": "Room", "worldX": 5}) == External("Room", 5)
    assert to_data(External("Room")) == {"__identifier": "Room", "worldX": 0}
    with pytest.raises(SerdeError) as info:
        from_data(External, {})
    assert info.value.path == "$.__identifier"
