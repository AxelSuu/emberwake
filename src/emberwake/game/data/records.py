"""Best results per run key (a trial, a speedrun category), persisted as ``records.json``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from emberwake.engine.core.serde import VersionedCodec
from emberwake.engine.platform.documents import load_document, save_document

if TYPE_CHECKING:
    from emberwake.engine.platform.storage import Storage

RECORDS_KEY = "records.json"


@dataclass(slots=True)
class RunResult:
    """What one finished run produced."""

    key: str
    """Which run this was, for example ``"trial/ascent"`` or ``"any%"``."""
    time: float
    """Seconds, in simulated time."""
    deaths: int = 0
    embers: int = 0
    medal: str = ""
    """``"gold"``, ``"silver"``, ``"bronze"`` or nothing."""


@dataclass(slots=True)
class Record:
    best_time: float
    deaths_at_best: int = 0
    plays: int = 1


@dataclass(slots=True)
class Records:
    runs: dict[str, Record] = field(default_factory=dict)
    unlocked: list[str] = field(default_factory=list)
    """Ids of locked trials that a trial door has opened."""


def _add_unlocked(data: dict[str, Any]) -> dict[str, Any]:
    """v1 -> v2: unlocked trials; none in older records."""
    return data


RECORDS_CODEC = VersionedCodec(Records, version=2, migrations={1: _add_unlocked})
"""Bump the version and add a migration whenever `Records` changes shape."""


def unlock(records: Records, trial_id: str) -> None:
    """Open a locked trial in the Trials menu."""
    if trial_id not in records.unlocked:
        records.unlocked.append(trial_id)


def submit(records: Records, result: RunResult) -> bool:
    """Fold `result` into `records`; returns whether it is a new best time."""
    record = records.runs.get(result.key)
    if record is None:
        records.runs[result.key] = Record(result.time, result.deaths)
        return True
    record.plays += 1
    if result.time < record.best_time:
        record.best_time, record.deaths_at_best = result.time, result.deaths
        return True
    return False


def load_records(storage: Storage) -> Records:
    return load_document(storage, RECORDS_KEY, RECORDS_CODEC, Records)


def save_records(storage: Storage, records: Records) -> None:
    save_document(storage, RECORDS_KEY, RECORDS_CODEC, records)


def format_time(seconds: float) -> str:
    """``m:ss.cc``, for results and records."""
    centis = round(seconds * 100)
    return f"{centis // 6000}:{centis // 100 % 60:02d}.{centis % 100:02d}"
