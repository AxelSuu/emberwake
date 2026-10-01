from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest
from tools.levels.source import RoomFile, SourceError, check_layout, load_source, make_room

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path

WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
ROOM = "\n".join([WALL, *[INSIDE] * 8, "#.P" + "." * 16 + "#", WALL])
"""A bare 20x11 room with a PlayerStart at (2, 9)."""


def put(text: str, x: int, y: int, chars: str) -> str:
    rows = text.strip().splitlines()
    rows[y] = rows[y][:x] + chars + rows[y][x + len(chars) :]
    return "\n".join(rows)


def room_file(text: str) -> RoomFile:
    return from_data(RoomFile, tomllib.loads(text))


def test_marker_blocks_become_entities_in_reading_order():
    text = put(put(put(ROOM, 5, 7, "b"), 5, 8, "b"), 5, 9, "b")
    text = put(put(text, 10, 9, "e"), 12, 9, "ee")
    toml = '[entities.b]\ntype = "Door"\n[entities.e]\ntype = "Ember"'
    room = make_room("R", (2, 1), text, room_file(toml))
    assert [(p.marker, p.type, p.column, p.row, p.columns, p.rows) for p in room.entities] == [
        ("b", "Door", 5, 7, 1, 3),
        ("P", "PlayerStart", 2, 9, 1, 1),
        ("e", "Ember", 10, 9, 1, 1),
        ("e", "Ember", 12, 9, 2, 1),
    ]
    assert [(p.index, p.count) for p in room.entities if p.marker == "e"] == [(0, 2), (1, 2)]
    assert room.size == (20, 11)
    assert room.world_px == (640, 176)


@pytest.mark.parametrize(
    ("text", "toml", "message"),
    [
        (put(ROOM, 1, 9, "!"), "", "unknown character"),
        (ROOM + "\n#", "", "equal length"),
        ("\n".join(line[:10] for line in ROOM.splitlines()), "", "whole number"),
        (put(ROOM, 3, 9, "z"), "", "no \\[entities.z\\]"),
        (ROOM, '[entities.z]\ntype = "Ember"', "not in the map"),
        (put(put(ROOM, 4, 9, "zz"), 4, 8, "z"), '[entities.z]\ntype = "Door"', "not a rectangle"),
    ],
)
def test_room_errors(text: str, toml: str, message: str):
    with pytest.raises(SourceError, match=message):
        make_room("Bad", (0, 0), text, room_file(toml))


def test_overlapping_rooms_are_an_error():
    rooms = [make_room("A", (0, 0), ROOM), make_room("B", (1, 0), ROOM)]
    check_layout(rooms)
    with pytest.raises(SourceError, match="A and C overlap"):
        check_layout([*rooms, make_room("C", (0, 0), ROOM)])


def test_load_source_reads_rooms_with_and_without_toml(tmp_path: Path):
    (tmp_path / "defs.toml").write_text('[entities.Ember]\ncolor = "#ea4f36"\n')
    (tmp_path / "world.toml").write_text("[rooms.A]\ncell = [0, 0]\n[rooms.B]\ncell = [1, 0]\n")
    (tmp_path / "a.txt").write_text(put(ROOM, 4, 9, "e"))
    (tmp_path / "a.toml").write_text('fields = { Mood = "calm" }\n[entities.e]\ntype = "Ember"\n')
    (tmp_path / "b.txt").write_text(ROOM)
    source = load_source(tmp_path)
    assert list(source.defs.entities) == ["Ember"]
    a, b = source.rooms
    assert a.fields == {"Mood": "calm"}
    assert [p.type for p in a.entities] == ["PlayerStart", "Ember"]
    assert (b.cell, b.fields) == ((1, 0), {})


def test_bad_toml_names_the_file(tmp_path: Path):
    (tmp_path / "defs.toml").write_text("entities = 3\n")
    with pytest.raises(SourceError, match=r"defs\.toml: \$\.entities"):
        load_source(tmp_path)
