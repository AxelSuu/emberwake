"""Behavior trees, for brains with more phases than a state machine keeps readable.

A `Tree` is ticked once per simulation step with a blackboard (the entity's own state, usually a
component) and the fixed dt. Every node returns `SUCCESS`, `FAILURE` or `RUNNING`. Leaves are
plain functions: a `Condition` asks the blackboard a question and an `Action` does one step of
work. `Sequence`, `Selector` and `Parallel` arrange children, `Cooldown` and `Repeat` wrap one.
Children run in order and nothing is random, so a tree is as deterministic as its leaves.

A `Sequence` or `Selector` remembers its running child and resumes it on the next tick. With
``reactive=True`` it starts from its first child on every tick instead, so guards are checked
again, and the running child is aborted when an earlier one takes over. `Tree.reset` aborts
whatever runs, as a boss does when it changes phase.

Nodes keep their run state themselves: build one tree per entity, from a function.

Example:
    >>> class Boss:
    ...     hp = 3
    >>> def wounded(boss):
    ...     return boss.hp < 3
    >>> def prowl(boss, dt, t):
    ...     return RUNNING
    >>> def lunge(boss, dt, t):
    ...     return SUCCESS if t >= 0.5 else RUNNING
    >>> tree = Tree(
    ...     Selector(Sequence(Condition(wounded), Action(lunge)), Action(prowl), reactive=True)
    ... )
    >>> boss = Boss()
    >>> tree.tick(boss, 0.25)
    <Status.RUNNING: 'running'>
    >>> boss.hp = 2
    >>> tree.tick(boss, 0.25)
    <Status.RUNNING: 'running'>
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

EPSILON = 1e-9
"""Slack for float error in cooldowns, so 0.5 s at 60 Hz ends on tick 30 and not 31."""


class Status(Enum):
    """What a node reports after a tick."""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


SUCCESS = Status.SUCCESS
FAILURE = Status.FAILURE
RUNNING = Status.RUNNING


class Context[B]:
    """What every node sees on one tick: blackboard, dt and the tree's clock in seconds."""

    __slots__ = ("bb", "dt", "now")

    def __init__(self, bb: B, dt: float, now: float) -> None:
        self.bb = bb
        self.dt = dt
        self.now = now


class Node[B]:
    """Base of every node.

    Subclasses override `_run` (one tick of work) and, if they hold run state, `_abort`.

    Attributes:
        children: The nodes below, in tick order.
        running: Whether the last tick returned `RUNNING` and no abort has happened since.
    """

    __slots__ = ("children", "running")

    def __init__(self, *children: Node[B]) -> None:
        self.children = children
        self.running = False

    def tick(self, ctx: Context[B]) -> Status:
        """Run one tick."""
        status = self._run(ctx)
        self.running = status is RUNNING
        return status

    def reset(self, bb: B) -> None:
        """Abort this node and what runs below it; a node that is not running is left alone."""
        if self.running:
            self.running = False
            self._abort(bb)

    def _run(self, ctx: Context[B]) -> Status:
        raise NotImplementedError

    def _abort(self, bb: B) -> None:
        for child in self.children:
            child.reset(bb)


class Condition[B](Node[B]):
    """Succeeds when ``fn(bb)`` is true and fails otherwise."""

    __slots__ = ("fn",)

    def __init__(self, fn: Callable[[B], bool]) -> None:
        super().__init__()
        self.fn = fn

    def _run(self, ctx: Context[B]) -> Status:
        return SUCCESS if self.fn(ctx.bb) else FAILURE


class Action[B](Node[B]):
    """Returns ``fn(bb, dt, t)`` on every tick.

    ``t`` is how long the action had been running before this tick, as in `Fsm`: 0.0 on its
    first tick (the place to start things) and growing while it returns `RUNNING`. It restarts
    at 0.0 once the action finishes or is aborted. ``on_abort(bb)`` runs when it is aborted
    while running.
    """

    __slots__ = ("elapsed", "fn", "on_abort")

    def __init__(
        self,
        fn: Callable[[B, float, float], Status],
        *,
        on_abort: Callable[[B], None] | None = None,
    ) -> None:
        super().__init__()
        self.fn = fn
        self.on_abort = on_abort
        self.elapsed = 0.0

    def _run(self, ctx: Context[B]) -> Status:
        status = self.fn(ctx.bb, ctx.dt, self.elapsed)
        self.elapsed = self.elapsed + ctx.dt if status is RUNNING else 0.0
        return status

    def _abort(self, bb: B) -> None:
        self.elapsed = 0.0
        if self.on_abort is not None:
            self.on_abort(bb)


class _Chain[B](Node[B]):
    """Children one after another while they return `_go`."""

    __slots__ = ("_go", "_index", "reactive")

    def __init__(self, go: Status, children: tuple[Node[B], ...], reactive: bool) -> None:
        super().__init__(*children)
        self._go = go
        self.reactive = reactive
        self._index = 0

    def _run(self, ctx: Context[B]) -> Status:
        kids = self.children
        was = self._index if self.running else -1
        i = 0 if self.reactive else self._index
        status = self._go
        while i < len(kids):
            status = kids[i].tick(ctx)
            if status is not self._go:
                break
            i += 1
        if was != i and was >= 0:
            kids[was].reset(ctx.bb)
        self._index = i if status is RUNNING else 0
        return status

    def _abort(self, bb: B) -> None:
        super()._abort(bb)
        self._index = 0


class Sequence[B](_Chain[B]):
    """Ticks its children in order while they succeed.

    Fails at the first child that fails and succeeds when all have succeeded (an empty sequence
    succeeds). In a reactive sequence the children before the running one run again on every
    tick, so they should be conditions.
    """

    __slots__ = ()

    def __init__(self, *children: Node[B], reactive: bool = False) -> None:
        super().__init__(SUCCESS, children, reactive)


class Selector[B](_Chain[B]):
    """Ticks its children in order until one does not fail.

    Succeeds at the first child that succeeds and fails when all have failed (an empty selector
    fails). A reactive selector is a priority list: a branch above the running one takes over
    as soon as it stops failing.
    """

    __slots__ = ()

    def __init__(self, *children: Node[B], reactive: bool = False) -> None:
        super().__init__(FAILURE, children, reactive)


class Parallel[B](Node[B]):
    """Ticks every unfinished child on each tick.

    Fails as soon as one child fails. Succeeds once every child has succeeded, or once one has
    with ``any_success=True`` (a main child that ends background ones). The children still
    running are aborted when it finishes.
    """

    __slots__ = ("_done", "any_success")

    def __init__(self, *children: Node[B], any_success: bool = False) -> None:
        super().__init__(*children)
        self.any_success = any_success
        self._done: list[Status | None] = [None] * len(children)

    def _run(self, ctx: Context[B]) -> Status:
        done = self._done
        for i, child in enumerate(self.children):
            if done[i] is None:
                status = child.tick(ctx)
                if status is not RUNNING:
                    done[i] = status
        if FAILURE in done:
            result = FAILURE
        elif (SUCCESS in done) if self.any_success else (None not in done):
            result = SUCCESS
        else:
            return RUNNING
        self._abort(ctx.bb)
        return result

    def _abort(self, bb: B) -> None:
        super()._abort(bb)
        self._done = [None] * len(self.children)


class Cooldown[B](Node[B]):
    """Fails without ticking its child for `seconds` after the child succeeds.

    A failure does not start the cooldown. It counts the tree's clock, so it runs out while
    nothing ticks it and a reset keeps it.
    """

    __slots__ = ("_ready", "seconds")

    def __init__(self, child: Node[B], seconds: float) -> None:
        super().__init__(child)
        self.seconds = seconds
        self._ready = -math.inf

    def _run(self, ctx: Context[B]) -> Status:
        if ctx.now + EPSILON < self._ready:
            return FAILURE
        status = self.children[0].tick(ctx)
        if status is SUCCESS:
            self._ready = ctx.now + self.seconds
        return status


class Repeat[B](Node[B]):
    """Runs its child again each time it succeeds: `times` runs in all, or forever if None.

    Succeeds after the last run and fails as soon as a run fails. The child runs at most once a
    tick (the repeat returns `RUNNING` in between), so an instant child never hangs the game.

    Raises:
        ValueError: If `times` is less than one.
    """

    __slots__ = ("_runs", "times")

    def __init__(self, child: Node[B], times: int | None = None) -> None:
        if times is not None and times < 1:
            raise ValueError(f"repeat needs at least one run, got {times}")
        super().__init__(child)
        self.times = times
        self._runs = 0

    def _run(self, ctx: Context[B]) -> Status:
        status = self.children[0].tick(ctx)
        if status is RUNNING:
            return RUNNING
        if status is SUCCESS:
            self._runs += 1
            if self._runs != self.times:
                return RUNNING
        self._runs = 0
        return status

    def _abort(self, bb: B) -> None:
        super()._abort(bb)
        self._runs = 0


class Tree[B]:
    """A root node and the clock its nodes share."""

    __slots__ = ("now", "root")

    def __init__(self, root: Node[B]) -> None:
        self.root = root
        self.now = 0.0
        """Seconds ticked so far."""

    def tick(self, bb: B, dt: float) -> Status:
        """Advance the clock by `dt` and tick the root with blackboard `bb`."""
        self.now += dt
        return self.root.tick(Context(bb, dt, self.now))

    def reset(self, bb: B) -> None:
        """Abort whatever is running; the next tick starts from the root again."""
        self.root.reset(bb)
