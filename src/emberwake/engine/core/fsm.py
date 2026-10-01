"""Finite state machines as tables of functions.

A state is a function ``(context, dt, time_in_state) -> next state name or None``. The machine
holds no state of its own: callers keep the current state's name (so it can live in a
component) and call `Fsm.step`, which runs the state and reports the new name.

Example:
    >>> def idle(ctx, dt, t):
    ...     return "walk" if t > 1 else None
    >>> def walk(ctx, dt, t):
    ...     return None
    >>> fsm = Fsm({"idle": idle, "walk": walk})
    >>> fsm.step(None, "idle", 0.5, 0.5)
    'idle'
    >>> fsm.step(None, "idle", 0.5, 1.5)
    'walk'
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

type StateFn[C] = Callable[[C, float, float], str | None]


@dataclass(slots=True)
class Fsm[C]:
    """A named set of states."""

    states: Mapping[str, StateFn[C]]

    def step(self, context: C, state: str, dt: float, time_in_state: float) -> str:
        """Run `state` once and return the state to be in next (the same one if it stays)."""
        if state not in self.states:
            raise KeyError(f"no state {state!r}; states are {sorted(self.states)}")
        nxt = self.states[state](context, dt, time_in_state)
        if nxt is not None and nxt not in self.states:
            raise KeyError(f"state {state!r} moved to unknown state {nxt!r}")
        return state if nxt is None else nxt
