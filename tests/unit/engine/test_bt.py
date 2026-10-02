from __future__ import annotations

import doctest
from dataclasses import dataclass, field

import pytest

from emberwake.engine.core import bt as bt_module
from emberwake.engine.core.bt import (
    FAILURE,
    RUNNING,
    SUCCESS,
    Action,
    Condition,
    Cooldown,
    Parallel,
    Repeat,
    Selector,
    Sequence,
    Status,
    Tree,
)

STEP = 1 / 60


@dataclass
class Board:
    hp: int = 3
    flags: dict[str, bool] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)


def steps(name: str, *statuses: Status) -> Action[Board]:
    """Logs its name each tick and returns `statuses` in turn, then the last one forever."""
    left = list(statuses)

    def fn(bb: Board, dt: float, t: float) -> Status:
        bb.log.append(name)
        return left.pop(0) if len(left) > 1 else left[0]

    return Action(fn, on_abort=lambda bb: bb.log.append(f"{name} aborted"))


def flag(name: str) -> Condition[Board]:
    def fn(bb: Board) -> bool:
        bb.log.append(f"{name}?")
        return bb.flags.get(name, False)

    return Condition(fn)


def run(tree: Tree[Board], bb: Board, ticks: int, dt: float = STEP) -> list[Status]:
    return [tree.tick(bb, dt) for _ in range(ticks)]


def test_docstring_example() -> None:
    assert doctest.testmod(bt_module).failed == 0


def test_a_sequence_runs_children_until_one_fails() -> None:
    bb = Board()
    tree = Tree(Sequence(steps("a", SUCCESS), steps("b", FAILURE), steps("c", SUCCESS)))
    assert tree.tick(bb, STEP) is FAILURE
    assert bb.log == ["a", "b"]
    assert Tree(Sequence[Board]()).tick(bb, STEP) is SUCCESS


def test_a_selector_runs_children_until_one_does_not_fail() -> None:
    bb = Board()
    tree = Tree(Selector(steps("a", FAILURE), steps("b", SUCCESS), steps("c", SUCCESS)))
    assert tree.tick(bb, STEP) is SUCCESS
    assert bb.log == ["a", "b"]
    assert Tree(Selector[Board]()).tick(bb, STEP) is FAILURE


def test_a_running_child_resumes_without_ticking_the_ones_before_it() -> None:
    bb = Board()
    tree = Tree(
        Sequence(steps("a", SUCCESS), steps("b", RUNNING, RUNNING, SUCCESS), steps("c", SUCCESS))
    )
    assert run(tree, bb, 3) == [RUNNING, RUNNING, SUCCESS]
    assert bb.log == ["a", "b", "b", "b", "c"]
    bb.log.clear()
    assert tree.tick(bb, STEP) is SUCCESS
    assert bb.log == ["a", "b", "c"], "a finished sequence starts over"


def test_a_reactive_sequence_aborts_its_running_child_when_a_guard_fails() -> None:
    bb = Board(flags={"awake": True})
    tree = Tree(Sequence(flag("awake"), steps("act", RUNNING), reactive=True))
    assert run(tree, bb, 2) == [RUNNING, RUNNING]
    bb.log.clear()
    bb.flags["awake"] = False
    assert tree.tick(bb, STEP) is FAILURE
    assert bb.log == ["awake?", "act aborted"]


def test_a_reactive_selector_lets_a_higher_branch_take_over() -> None:
    bb = Board()
    tree = Tree(
        Selector(
            Sequence(flag("hurt"), steps("flinch", RUNNING, SUCCESS)),
            steps("prowl", RUNNING),
            reactive=True,
        )
    )
    tree.tick(bb, STEP)
    bb.log.clear()
    bb.flags["hurt"] = True
    assert tree.tick(bb, STEP) is RUNNING
    assert bb.log == ["hurt?", "flinch", "prowl aborted"]
    bb.log.clear()
    bb.flags["hurt"] = False
    assert tree.tick(bb, STEP) is SUCCESS
    assert bb.log == ["flinch"], "a memory sequence resumes its child without the guard"


def test_a_selector_without_reactive_keeps_its_running_child() -> None:
    bb = Board()
    tree = Tree(Selector(Sequence(flag("hurt"), steps("flinch", SUCCESS)), steps("prowl", RUNNING)))
    tree.tick(bb, STEP)
    bb.flags["hurt"] = True
    bb.log.clear()
    run(tree, bb, 3)
    assert bb.log == ["prowl"] * 3


def test_a_branch_that_takes_over_again_starts_fresh() -> None:
    times: list[float] = []

    def prowl(bb: Board, dt: float, t: float) -> Status:
        times.append(t)
        return RUNNING

    bb = Board()
    tree = Tree(
        Selector(Sequence(flag("hurt"), steps("flinch", SUCCESS)), Action(prowl), reactive=True)
    )
    run(tree, bb, 3, dt=0.5)
    bb.flags["hurt"] = True
    tree.tick(bb, 0.5)
    bb.flags["hurt"] = False
    run(tree, bb, 2, dt=0.5)
    assert times == [0.0, 0.5, 1.0, 0.0, 0.5]


def test_three_phases_switch_on_health_and_abort_the_last() -> None:
    def fight() -> list[str]:
        bb = Board()
        tree = Tree(
            Selector(
                Sequence(Condition(lambda b: b.hp < 2), steps("drain", RUNNING)),
                Sequence(Condition(lambda b: b.hp < 3), steps("dark water", RUNNING)),
                Selector(
                    Cooldown(steps("lunge", SUCCESS), 0.5), steps("circle", RUNNING), reactive=True
                ),
                reactive=True,
            )
        )
        run(tree, bb, 60)
        assert bb.log.count("lunge") == 2
        bb.log.clear()
        bb.hp = 2
        run(tree, bb, 2)
        bb.hp = 1
        tree.tick(bb, STEP)
        return bb.log

    log = fight()
    assert log == ["dark water", "circle aborted", "dark water", "drain", "dark water aborted"]
    assert fight() == log, "same inputs, same fight"


def test_parallel_needs_all_successes_and_fails_on_any_failure() -> None:
    bb = Board()
    tree = Tree(Parallel(steps("a", RUNNING, SUCCESS), steps("b", SUCCESS)))
    assert run(tree, bb, 2) == [RUNNING, SUCCESS]
    assert bb.log == ["a", "b", "a"], "a finished child is not ticked again"

    bb = Board()
    tree = Tree(Parallel(steps("a", RUNNING), steps("b", RUNNING, FAILURE)))
    assert run(tree, bb, 2) == [RUNNING, FAILURE]
    assert bb.log == ["a", "b", "a", "b", "a aborted"]


def test_parallel_any_success_lets_a_main_child_end_a_background_one() -> None:
    bb = Board()
    lunge, glow = steps("lunge", RUNNING, SUCCESS), steps("glow", RUNNING)
    tree = Tree(Parallel(lunge, glow, any_success=True))
    assert run(tree, bb, 2) == [RUNNING, SUCCESS]
    assert bb.log == ["lunge", "glow", "lunge", "glow", "glow aborted"]
    bb.log.clear()
    assert tree.tick(bb, STEP) is SUCCESS, "it starts over after finishing"
    assert bb.log == ["lunge", "glow", "glow aborted"]


def test_a_condition_asks_the_blackboard() -> None:
    bb = Board(hp=1)
    assert Tree(Condition[Board](lambda b: b.hp > 0)).tick(bb, STEP) is SUCCESS
    assert Tree(Condition[Board](lambda b: b.hp > 1)).tick(bb, STEP) is FAILURE


def test_an_action_gets_the_blackboard_dt_and_its_running_time() -> None:
    seen: list[tuple[Board, float, float]] = []

    def swim(bb: Board, dt: float, t: float) -> Status:
        seen.append((bb, dt, t))
        return SUCCESS if len(seen) % 3 == 0 else RUNNING

    bb = Board()
    run(Tree(Action(swim)), bb, 4, dt=0.25)
    assert seen == [(bb, 0.25, 0.0), (bb, 0.25, 0.25), (bb, 0.25, 0.5), (bb, 0.25, 0.0)]


def test_a_cooldown_blocks_its_child_after_a_success() -> None:
    bb = Board()
    tree = Tree(Cooldown(steps("bite", SUCCESS), 0.5))
    statuses = run(tree, bb, 61)
    assert [i + 1 for i, s in enumerate(statuses) if s is SUCCESS] == [1, 31, 61]
    assert bb.log == ["bite"] * 3


def test_a_failure_does_not_start_the_cooldown() -> None:
    bb = Board()
    tree = Tree(Cooldown(Sequence(flag("near"), steps("bite", SUCCESS)), 1.0))
    assert run(tree, bb, 3) == [FAILURE] * 3
    bb.flags["near"] = True
    assert tree.tick(bb, STEP) is SUCCESS


def test_a_cooldown_runs_out_while_nothing_ticks_it_and_survives_a_reset() -> None:
    bb = Board(flags={"near": True})
    tree = Tree(Sequence(flag("near"), Cooldown(steps("bite", SUCCESS), 0.5)))
    assert tree.tick(bb, STEP) is SUCCESS
    tree.reset(bb)
    assert tree.tick(bb, STEP) is FAILURE
    bb.flags["near"] = False
    run(tree, bb, 40)
    bb.flags["near"] = True
    assert tree.tick(bb, STEP) is SUCCESS
    assert bb.log.count("bite") == 2


def test_repeat_runs_its_child_once_a_tick_and_then_succeeds() -> None:
    bb = Board()
    tree = Tree(Repeat(steps("hop", SUCCESS), 3))
    assert run(tree, bb, 4) == [RUNNING, RUNNING, SUCCESS, RUNNING]
    assert bb.log == ["hop"] * 4


def test_repeat_fails_when_a_run_fails() -> None:
    tree = Tree(Repeat(steps("hop", SUCCESS, FAILURE, SUCCESS), 3))
    assert run(tree, Board(), 4) == [RUNNING, FAILURE, RUNNING, RUNNING]


def test_repeat_forever_runs_an_instant_child_once_a_tick() -> None:
    bb = Board()
    assert set(run(Tree(Repeat(steps("hop", SUCCESS))), bb, 500)) == {RUNNING}
    assert len(bb.log) == 500


def test_repeat_forgets_its_count_when_aborted() -> None:
    bb = Board()
    tree = Tree(Repeat(steps("hop", SUCCESS), 3))
    run(tree, bb, 2)
    tree.reset(bb)
    assert run(tree, bb, 3) == [RUNNING, RUNNING, SUCCESS]


def test_repeat_needs_a_run() -> None:
    with pytest.raises(ValueError, match="at least one"):
        Repeat(steps("hop", SUCCESS), 0)


def test_reset_aborts_what_runs_and_starts_over() -> None:
    bb = Board()
    tree = Tree(Sequence(steps("a", SUCCESS), steps("b", RUNNING)))
    tree.tick(bb, STEP)
    tree.reset(bb)
    tree.reset(bb)
    tree.tick(bb, STEP)
    assert bb.log == ["a", "b", "b aborted", "a", "b"]


def test_a_subtree_resets_for_a_phase_change() -> None:
    bb = Board()
    phase = Sequence(steps("rise", SUCCESS), steps("lunge", RUNNING))
    tree = Tree(Parallel(phase, steps("glow", RUNNING)))
    run(tree, bb, 2)
    bb.log.clear()
    phase.reset(bb)
    tree.tick(bb, STEP)
    assert bb.log == ["lunge aborted", "rise", "lunge", "glow"]


def test_the_tree_keeps_time() -> None:
    tree = Tree(steps("a", RUNNING))
    run(tree, Board(), 3, dt=0.25)
    assert tree.now == 0.75
