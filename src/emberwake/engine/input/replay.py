"""Record and replay per-tick action frames.

Frames are run-length encoded: ``[[12, ["right"]], [3, ["jump", "right"]]]`` means 12 ticks of
right, then 3 ticks of jump and right. A minute of play is usually a few hundred bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import VersionedCodec

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(slots=True)
class Replay:
    """A recorded run.

    Attributes:
        start: What the run starts from, such as a room identifier.
        seed: Seed of the run's random generators.
        runs: ``(tick_count, sorted action values)`` pairs.
    """

    start: str = ""
    seed: int = 0
    runs: list[tuple[int, list[str]]] = field(default_factory=list)

    @property
    def ticks(self) -> int:
        """Total number of recorded ticks."""
        return sum(count for count, _ in self.runs)


REPLAY_CODEC = VersionedCodec(Replay, version=1)


class ReplayRecorder[A: Enum]:
    """Appends one frame per tick to a `Replay`."""

    def __init__(self, start: str = "", seed: int = 0) -> None:
        self.replay = Replay(start, seed)

    def record(self, frame: frozenset[A]) -> None:
        """Append the frame of the current tick."""
        values = sorted(str(action.value) for action in frame)
        runs = self.replay.runs
        if runs and runs[-1][1] == values:
            runs[-1] = (runs[-1][0] + 1, values)
        else:
            runs.append((1, values))


class ReplayPlayer[A: Enum]:
    """Yields the recorded frames of a `Replay` one tick at a time."""

    def __init__(self, replay: Replay, actions: type[A]) -> None:
        self._frames = _decode(replay, actions)
        self.finished = False

    def sample(self) -> frozenset[A]:
        """The next frame, or an empty frame once the replay is over."""
        frame = next(self._frames, None)
        if frame is None:
            self.finished = True
            return frozenset()
        return frame


def _decode[A: Enum](replay: Replay, actions: type[A]) -> Iterator[frozenset[A]]:
    for count, values in replay.runs:
        frame = frozenset(actions(value) for value in values)
        for _ in range(count):
            yield frame
