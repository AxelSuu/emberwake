"""Data-driven sprite animation with per-frame events and hitboxes.

Clips are plain data (usually from TOML), so timing and tags are tuned without code. An
`Animator` plays one clip at a time and reports the events tagged on each frame it enters,
such as ``footstep`` or ``hit``, exactly once, even when a long step skips frames.

Example:
    >>> clips = {"run": Clip(frames=[0, 1, 2, 3], ms=100, events={1: "footstep", 3: "footstep"})}
    >>> animator = Animator(clips)
    >>> animator.play("run")
    >>> [e.name for e in animator.update(0.25)]
    ['footstep']
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path

type Box = tuple[int, int, int, int]
"""A rectangle ``(x, y, width, height)`` in px, relative to the sprite's top left."""


@dataclass(slots=True)
class Clip:
    """One animation.

    Attributes:
        frames: Sheet frame indices in play order.
        ms: Milliseconds each frame is shown.
        loop: Whether to wrap around; otherwise the last frame holds and `finished` is set.
        events: Event names by position in `frames`, fired when that position is entered.
        hitboxes: Boxes by position in `frames`, active while that position shows.
    """

    frames: list[int]
    ms: int = 100
    loop: bool = True
    events: dict[int, str] = field(default_factory=dict)
    hitboxes: dict[int, list[Box]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("a clip needs at least one frame")
        if self.ms <= 0:
            raise ValueError(f"ms must be positive, not {self.ms}")


@dataclass(frozen=True, slots=True)
class AnimEvent:
    """A tagged frame was entered."""

    name: str
    clip: str
    frame: int


def load_clips(path: Path) -> dict[str, Clip]:
    """Parse a TOML file of named clips. Raises `tomllib.TOMLDecodeError` or `SerdeError`."""
    return from_data(dict[str, Clip], tomllib.loads(path.read_text(encoding="utf-8")))


class Animator:
    """Plays clips from a table and reports frame events."""

    def __init__(self, clips: dict[str, Clip]) -> None:
        self.clips = clips
        self.name = ""
        self.position = 0
        self.finished = False
        self._elapsed = 0.0
        self._pending: list[AnimEvent] = []

    @property
    def clip(self) -> Clip | None:
        """The playing clip, if any."""
        return self.clips.get(self.name)

    @property
    def frame(self) -> int:
        """The sheet frame to draw (0 before any clip plays)."""
        clip = self.clip
        return clip.frames[self.position] if clip else 0

    @property
    def hitboxes(self) -> list[Box]:
        """The boxes active on the current frame."""
        clip = self.clip
        return clip.hitboxes.get(self.position, []) if clip else []

    def play(self, name: str, *, restart: bool = False) -> None:
        """Start `name`. Asking for the clip already playing does nothing unless `restart`."""
        if name not in self.clips:
            raise KeyError(f"no clip {name!r}")
        if name == self.name and not restart:
            return
        self.name, self.position, self.finished, self._elapsed = name, 0, False, 0.0
        self._pending = []
        self._enter(0)

    def update(self, dt: float) -> list[AnimEvent]:
        """Advance by `dt` seconds; return the events of every frame entered, in order."""
        clip = self.clip
        if clip is not None and not self.finished:
            self._elapsed += dt * 1000
            while self._elapsed >= clip.ms and not self.finished:
                self._elapsed -= clip.ms
                self._advance(clip)
        events, self._pending = self._pending, []
        return events

    def _advance(self, clip: Clip) -> None:
        nxt = self.position + 1
        if nxt >= len(clip.frames):
            if not clip.loop:
                self.finished = True
                return
            nxt = 0
        self.position = nxt
        self._enter(nxt)

    def _enter(self, position: int) -> None:
        clip = self.clip
        if clip is not None and position in clip.events:
            self._pending.append(AnimEvent(clip.events[position], self.name, position))
