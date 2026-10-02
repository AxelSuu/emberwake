from __future__ import annotations

from emberwake.engine.platform.storage import MemoryStorage
from emberwake.game.data.records import (
    RECORDS_KEY,
    Records,
    RunResult,
    format_time,
    load_records,
    save_records,
    submit,
    unlock,
)


def test_first_result_is_a_best() -> None:
    records = Records()
    assert submit(records, RunResult("a", 61.5, deaths=2))
    assert records.runs["a"].best_time == 61.5
    assert records.runs["a"].plays == 1


def test_only_faster_runs_replace_the_best() -> None:
    records = Records()
    submit(records, RunResult("a", 60, deaths=3))
    assert not submit(records, RunResult("a", 70, deaths=0))
    assert records.runs["a"].best_time == 60
    assert submit(records, RunResult("a", 50, deaths=1))
    assert (records.runs["a"].best_time, records.runs["a"].deaths_at_best) == (50, 1)
    assert records.runs["a"].plays == 3


def test_keys_are_independent() -> None:
    records = Records()
    submit(records, RunResult("a", 60))
    assert submit(records, RunResult("b", 90))


def test_records_round_trip_through_storage() -> None:
    storage = MemoryStorage()
    records = Records()
    submit(records, RunResult("trial/ascent", 42.25, deaths=4))
    save_records(storage, records)
    assert load_records(storage).runs["trial/ascent"].best_time == 42.25
    assert load_records(MemoryStorage()).runs == {}


def test_format_time() -> None:
    assert format_time(0) == "0:00.00"
    assert format_time(61.5) == "1:01.50"
    assert format_time(3599.99) == "59:59.99"


def test_unlocking_is_kept_once_and_saved() -> None:
    storage = MemoryStorage()
    records = Records()
    unlock(records, "pits")
    unlock(records, "pits")
    save_records(storage, records)
    assert load_records(storage).unlocked == ["pits"]


def test_records_from_before_unlocking_still_load() -> None:
    storage = MemoryStorage()
    storage.write(RECORDS_KEY, '{"version": 1, "data": {"runs": {"a": {"best_time": 5.0}}}}')
    records = load_records(storage)
    assert records.runs["a"].best_time == 5.0
    assert records.unlocked == []
