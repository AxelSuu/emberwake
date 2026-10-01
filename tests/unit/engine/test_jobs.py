from __future__ import annotations

import doctest
from typing import TYPE_CHECKING

from emberwake.engine.core import jobs as jobs_module
from emberwake.engine.core.jobs import Jobs

if TYPE_CHECKING:
    from collections.abc import Iterator


def steps(name: str, n: int, log: list[str]) -> Iterator[None]:
    for i in range(n):
        log.append(f"{name}{i}")
        yield


class FakeClock:
    def __init__(self, tick: float) -> None:
        self.now, self.tick = 0.0, tick

    def __call__(self) -> float:
        self.now += self.tick
        return self.now


def test_docstring_example():
    assert doctest.testmod(jobs_module).failed == 0


def test_runs_jobs_in_order_within_the_budget():
    log: list[str] = []
    jobs = Jobs(clock=FakeClock(1.0))
    jobs.add(steps("a", 2, log))
    jobs.add(steps("b", 2, log))
    assert jobs.pump(budget=0.5) == 1
    assert jobs.pump(budget=0.5) == 1
    assert log == ["a0", "a1"]
    assert jobs.pump(budget=100) == 2
    assert log == ["a0", "a1", "b0", "b1"]
    assert len(jobs) == 0


def test_always_makes_one_step():
    log: list[str] = []
    jobs = Jobs(clock=FakeClock(10.0))
    jobs.add(steps("a", 3, log))
    assert jobs.pump(budget=0) == 1


def test_cancel():
    log: list[str] = []
    jobs = Jobs()
    job = steps("a", 3, log)
    jobs.add(job)
    jobs.cancel(job)
    jobs.cancel(job)
    assert jobs.pump(budget=1) == 0
    assert log == []
