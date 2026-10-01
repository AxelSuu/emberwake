"""Scripted sequences written as generators.

A script is a generator that yields what it waits for. Plain Python does the rest: loops,
branches, calling other scripts with ``yield from``. The simulation advances scripts with its
fixed time step, so a cutscene is as deterministic as the rest of the game.

Example:
    >>> log = []
    >>> def intro():
    ...     log.append("fade")
    ...     yield wait(0.5)
    ...     log.append("talk")
    ...     yield wait(0.5)
    ...     log.append("done")
    >>> player = CutscenePlayer()
    >>> _ = player.play(intro())
    >>> player.update(0.5), log
    (None, ['fade', 'talk'])
    >>> player.update(0.5), log
    (None, ['fade', 'talk', 'done'])
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

EPSILON = 1e-9
"""Slack for float error, so ten waits of 0.1 s take 60 steps and not 61."""
SKIP_LIMIT = 10_000
"""Most steps `Cutscene.skip` takes, so a script that never ends cannot hang the game."""


@dataclass(frozen=True, slots=True)
class Wait:
    """Resume after `seconds`."""

    seconds: float


@dataclass(frozen=True, slots=True)
class Until:
    """Resume when `condition` is true."""

    condition: Callable[[], bool]


@dataclass(frozen=True, slots=True)
class All:
    """Resume when every script has finished."""

    scripts: tuple[Script, ...]


type Command = Wait | Until | All | None
type Script = Iterator[Command]


def wait(seconds: float) -> Wait:
    """Pause the script for `seconds` of simulated time."""
    return Wait(seconds)


def until(condition: Callable[[], bool]) -> Until:
    """Pause the script until `condition()` is true, checked every step."""
    return Until(condition)


def together(*scripts: Script) -> All:
    """Run `scripts` side by side and continue when every one has finished."""
    return All(scripts)


class Cutscene:
    """One running script. Yielding ``None`` waits a single step."""

    def __init__(self, script: Script) -> None:
        self._script = script
        self._wait: Wait | None = None
        self._until: Until | None = None
        self._children: list[Cutscene] = []
        self._left = 0.0
        self._carry = 0.0
        """Time a finished wait overshot by, taken off the next wait so steps do not drift."""
        self.finished = False
        self.skipping = False

    def update(self, dt: float) -> None:
        """Advance by `dt`, running the script until it waits again."""
        if self.finished:
            return
        if self._children:
            for child in self._children:
                child.update(dt)
            self._children = [c for c in self._children if not c.finished]
            if self._children:
                return
        elif self._until is not None:
            if not (self.skipping or self._until.condition()):
                return
            self._until = None
        elif self._wait is not None:
            self._left -= dt
            if self._left > EPSILON and not self.skipping:
                return
            self._carry = 0.0 if self.skipping else -self._left
            self._wait = None
        self._run()

    def skip(self) -> None:
        """Finish at once: every wait ends immediately, so the script reaches its final state."""
        self.skipping = True
        steps = 0
        while not self.finished and steps < SKIP_LIMIT:
            self.update(0.0)
            steps += 1
        self.finished = True

    def _run(self) -> None:
        try:
            command = next(self._script)
        except StopIteration:
            self.finished = True
            return
        match command:
            case Wait(seconds):
                self._left = seconds - self._carry
                self._carry = 0.0
                self._wait = command if self._left > EPSILON else None
            case Until():
                self._until = command
            case All(scripts):
                self._children = [Cutscene(s) for s in scripts]
                for child in self._children:
                    child.skipping = self.skipping
                    child.update(0.0)
                self._children = [c for c in self._children if not c.finished]
            case _:
                pass


class CutscenePlayer:
    """Runs cutscenes one after another or together, and tells the game when to lock input."""

    def __init__(self) -> None:
        self._scenes: list[tuple[Cutscene, Callable[[], None] | None]] = []

    @property
    def active(self) -> bool:
        """Whether any cutscene is running."""
        return bool(self._scenes)

    def play(self, script: Script, on_done: Callable[[], None] | None = None) -> Cutscene:
        """Start `script` now; it runs until its first wait before this returns."""
        scene = Cutscene(script)
        self._scenes.append((scene, on_done))
        scene.update(0.0)
        self._sweep()
        return scene

    def update(self, dt: float) -> None:
        """Advance every running cutscene."""
        for scene, _ in list(self._scenes):
            scene.update(dt)
        self._sweep()

    def skip(self) -> None:
        """Skip every running cutscene to its end."""
        for scene, _ in list(self._scenes):
            scene.skip()
        self._sweep()

    def _sweep(self) -> None:
        done = [(scene, cb) for scene, cb in self._scenes if scene.finished]
        self._scenes = [(scene, cb) for scene, cb in self._scenes if not scene.finished]
        for _, callback in done:
            if callback:
                callback()
