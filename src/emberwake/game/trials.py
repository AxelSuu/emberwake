"""Trials: timed challenge rooms with medals, and ghosts of the best run.

A trial is a room with a `Goal`. The player starts at its PlayerStart, the clock runs while the
simulation does, and touching the goal ends the trial. The best run is saved as a replay; on the
next attempt a `Ghost` plays it back beside the player.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import component
from emberwake.engine.input import InputState
from emberwake.engine.input.replay import REPLAY_CODEC, ReplayPlayer
from emberwake.engine.physics import Body
from emberwake.engine.platform.documents import load_document, save_document
from emberwake.game.actions import Action
from emberwake.game.interact import Interactable, overlap, player_body
from emberwake.game.player.controller import new_player, step

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.engine.ecs import World
    from emberwake.engine.input.replay import Replay
    from emberwake.engine.physics import TileSource
    from emberwake.engine.platform.storage import Storage
    from emberwake.game.player.tuning import PlayerTuning

MEDALS = ("gold", "silver", "bronze")
KEY_PREFIX = "trial/"


@dataclass(slots=True)
class Trial:
    """A challenge: which room, and the slowest time that earns each medal."""

    room: str
    gold: float
    silver: float
    bronze: float
    locked: bool = False
    """Listed in the Trials menu only once a trial door has unlocked it."""


@dataclass(slots=True)
class TrialFile:
    trials: dict[str, Trial] = field(default_factory=dict)


def load_trials(path: Path) -> dict[str, Trial]:
    """Parse ``content/trials.toml``. Raises `tomllib.TOMLDecodeError` or `SerdeError`."""
    return from_data(TrialFile, {"trials": tomllib.loads(path.read_text(encoding="utf-8"))}).trials


def listed(trial_id: str, trial: Trial, unlocked: list[str]) -> bool:
    """Whether the Trials menu shows `trial`."""
    return not trial.locked or trial_id in unlocked


def record_key(trial_id: str) -> str:
    """The key a trial's results are stored under in ``records.json``."""
    return f"{KEY_PREFIX}{trial_id}"


def medal_for(trial: Trial, seconds: float) -> str:
    """``"gold"``, ``"silver"``, ``"bronze"`` or ``""`` for a time."""
    for medal in MEDALS:
        if seconds <= getattr(trial, medal):
            return medal
    return ""


def ghost_key(trial_id: str) -> str:
    return f"ghosts/{trial_id}.json"


def load_ghost(storage: Storage, trial_id: str) -> Replay | None:
    """The saved best run of a trial, if there is one."""
    return load_document(storage, ghost_key(trial_id), REPLAY_CODEC, lambda: None)


def save_ghost(storage: Storage, trial_id: str, replay: Replay) -> None:
    """Keep `replay` as the trial's ghost."""
    save_document(storage, ghost_key(trial_id), REPLAY_CODEC, replay)


@component
@dataclass(slots=True)
class Goal:
    """The finish line: touching it ends a trial."""


@dataclass(frozen=True, slots=True)
class GoalReached:
    """The player touched a goal."""


@component
@dataclass(slots=True)
class TrialDoor:
    """Interact to unlock `trial` in the menu and start it."""

    trial: str = ""


@dataclass(frozen=True, slots=True)
class TrialDoorUsed:
    trial: str


def trial_door_system(world: World, dt: float) -> None:
    """Publish `TrialDoorUsed` for each door the player used."""
    for _, interactable, door in world.query(Interactable, TrialDoor):
        if interactable.used:
            world.resource(EventBus).publish(TrialDoorUsed(door.trial))


def goal_system(world: World, dt: float) -> None:
    """Publish `GoalReached` while the living player overlaps a goal."""
    player = player_body(world)
    if player is None:
        return
    for _, body, _goal in world.query(Body, Goal):
        if overlap(body, player):
            world.resource(EventBus).publish(GoalReached())
            return


class Ghost:
    """A recorded run played back by its own body and controller.

    It runs the same movement code on the same input, so it follows the recorded path as long
    as the room is the same. It never touches the world's entities.
    """

    def __init__(self, replay: Replay, feet: tuple[float, float], tuning: PlayerTuning) -> None:
        self.body, self.motor = new_player(*feet, tuning)
        self._frames = ReplayPlayer(replay, Action)
        self._actions = InputState[Action]()
        self._tuning = tuning

    @property
    def finished(self) -> bool:
        """The recording ran out."""
        return self._frames.finished

    def update(self, grid: TileSource, dt: float) -> None:
        """Advance one tick (nothing once the replay is over)."""
        if self._frames.finished or self.motor.dead:
            return
        frame = self._frames.sample()
        if self._frames.finished:
            return
        self._actions.advance(frame)
        step(self.body, self.motor, self._actions, grid, self._tuning, dt)
