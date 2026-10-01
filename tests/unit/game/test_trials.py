from __future__ import annotations

import pytest
from tests.unit.game.test_strings import TABLES

from emberwake.engine.input.replay import Replay
from emberwake.engine.physics import Tile
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.game import paths
from emberwake.game.player.tuning import PlayerTuning
from emberwake.game.trials import (
    Ghost,
    Trial,
    ghost_key,
    load_ghost,
    load_trials,
    medal_for,
    record_key,
    save_ghost,
)

TRIAL = Trial(room="R", gold=10.0, silver=15.0, bronze=20.0)


@pytest.mark.parametrize(
    ("seconds", "medal"),
    [(5, "gold"), (10, "gold"), (10.01, "silver"), (15, "silver"), (20, "bronze"), (20.5, "")],
)
def test_medals(seconds: float, medal: str) -> None:
    assert medal_for(TRIAL, seconds) == medal


def test_keys() -> None:
    assert record_key("sprint") == "trial/sprint"
    assert ghost_key("sprint") == "ghosts/sprint.json"


def test_shipped_trials_load_with_ordered_medals_and_names() -> None:
    trials = load_trials(paths.content("trials.toml"))
    assert {"sprint", "pits"} <= set(trials)
    for ident, trial in trials.items():
        assert trial.gold < trial.silver < trial.bronze, ident
        for language, table in TABLES.items():
            assert table[f"trial.{ident}.name"], (language, ident)


def test_ghosts_round_trip_through_storage() -> None:
    storage = MemoryStorage()
    assert load_ghost(storage, "sprint") is None
    save_ghost(storage, "sprint", Replay("R", 0, [(30, ["right"]), (5, [])]))
    ghost = load_ghost(storage, "sprint")
    assert ghost is not None
    assert ghost.ticks == 35


class Floor:
    tile_size = 16

    def get(self, column: int, row: int) -> Tile:
        return Tile.SOLID if row >= 5 else Tile.EMPTY

    def void(self, x: float, y: float) -> bool:
        return False


def test_a_ghost_replays_its_input_and_stops_when_it_ends() -> None:
    replay = Replay("R", 0, [(30, ["right"])])
    ghost = Ghost(replay, (20.0, 80.0), PlayerTuning())
    start = ghost.body.x
    for _ in range(30):
        ghost.update(Floor(), 1 / 60)
    assert ghost.body.x > start + 40
    assert not ghost.finished
    ghost.update(Floor(), 1 / 60)
    assert ghost.finished
    stopped = ghost.body.x
    ghost.update(Floor(), 1 / 60)
    assert ghost.body.x == stopped
