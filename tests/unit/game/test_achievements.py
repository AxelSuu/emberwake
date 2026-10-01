from __future__ import annotations

import pytest
from tests.unit.game.test_strings import TABLES

from emberwake.engine.platform.storage import MemoryStorage
from emberwake.game import paths
from emberwake.game.achievements import ACHIEVEMENTS_KEY, Achievements, Def, load_defs

DEFS = {
    "jumper": Def(event="Jumped", count=3),
    "wanderer": Def(rooms=2),
    "greedy": Def(event="Collected", count=10),
}


def test_an_achievement_unlocks_when_its_counter_reaches_the_target() -> None:
    tracker = Achievements(DEFS)
    assert tracker.record("Jumped") == []
    assert tracker.record("Jumped") == []
    assert tracker.record("Jumped") == ["jumper"]
    assert tracker.unlocked("jumper")
    assert tracker.progress("jumper") == (3, 3)


def test_it_unlocks_only_once() -> None:
    tracker = Achievements(DEFS)
    tracker.record("Jumped", 3)
    assert tracker.record("Jumped") == []
    assert tracker.data.unlocked == ["jumper"]
    assert tracker.progress("jumper") == (3, 3)


def test_amounts_count_in_bulk() -> None:
    tracker = Achievements(DEFS)
    assert tracker.record("Collected", 12) == ["greedy"]


def test_room_achievements_count_different_rooms() -> None:
    tracker = Achievements(DEFS)
    assert tracker.enter_room("A") == []
    assert tracker.enter_room("A") == []
    assert tracker.progress("wanderer") == (1, 2)
    assert tracker.enter_room("B") == ["wanderer"]


def test_unrelated_events_change_nothing() -> None:
    tracker = Achievements(DEFS)
    tracker.record("Died", 99)
    assert not tracker.data.unlocked
    assert tracker.counter("Died") == 99
    assert tracker.counter("Nope") == 0


def test_the_callback_hears_each_unlock() -> None:
    heard: list[str] = []
    tracker = Achievements(DEFS, on_unlock=heard.append)
    tracker.record("Jumped", 3)
    tracker.record("Collected", 10)
    assert heard == ["jumper", "greedy"]


def test_unlocks_are_saved_at_once_and_loaded_back() -> None:
    storage = MemoryStorage()
    tracker = Achievements.load(DEFS, storage)
    tracker.record("Jumped", 3)
    assert storage.read(ACHIEVEMENTS_KEY) is not None
    again = Achievements.load(DEFS, storage)
    assert again.unlocked("jumper")
    assert again.counter("Jumped") == 3
    again.enter_room("X")
    again.save()
    assert Achievements.load(DEFS, storage).data.rooms == ["X"]


def test_a_missing_or_corrupt_file_starts_fresh() -> None:
    storage = MemoryStorage()
    assert not Achievements.load(DEFS, storage).data.unlocked
    storage.write(ACHIEVEMENTS_KEY, "{not json")
    assert not Achievements.load(DEFS, storage).data.unlocked


def test_nothing_is_saved_without_storage() -> None:
    tracker = Achievements(DEFS)
    tracker.record("Jumped", 3)
    tracker.save()


def test_shipped_achievements_load_and_have_text_in_every_language() -> None:
    defs = load_defs(paths.content("achievements.toml"))
    assert defs
    for ident, spec in defs.items():
        assert spec.target > 0
        assert spec.event or spec.rooms, ident
        for language, table in TABLES.items():
            assert table[f"achievement.{ident}.name"], (language, ident)
            assert table[f"achievement.{ident}.desc"], (language, ident)


def test_progress_of_an_unknown_achievement_is_an_error() -> None:
    with pytest.raises(KeyError):
        Achievements(DEFS).progress("nope")
