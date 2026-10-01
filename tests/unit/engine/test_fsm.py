from __future__ import annotations

import pytest

from emberwake.engine.core.fsm import Fsm


def test_a_state_can_stay_or_move() -> None:
    fsm = Fsm({"a": lambda c, dt, t: "b" if t >= 1 else None, "b": lambda c, dt, t: None})
    assert fsm.step(None, "a", 0.1, 0.5) == "a"
    assert fsm.step(None, "a", 0.1, 1.0) == "b"
    assert fsm.step(None, "b", 0.1, 9.0) == "b"


def test_states_get_the_context_and_dt() -> None:
    seen: list[tuple[object, float, float]] = []

    def state(ctx: object, dt: float, t: float) -> None:
        seen.append((ctx, dt, t))

    Fsm({"s": state}).step("ctx", "s", 0.25, 2.0)
    assert seen == [("ctx", 0.25, 2.0)]


def test_unknown_states_are_errors() -> None:
    fsm = Fsm({"a": lambda c, dt, t: "ghost"})
    with pytest.raises(KeyError, match="no state"):
        fsm.step(None, "x", 0, 0)
    with pytest.raises(KeyError, match="unknown state"):
        fsm.step(None, "a", 0, 0)
