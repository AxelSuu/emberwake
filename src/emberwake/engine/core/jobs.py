"""Long work split across frames: generators advanced under a time budget.

Each `next()` of a job should do one small, bounded piece of work. `Jobs.pump` advances jobs
in the order they were added until the budget runs out, always making at least one step so
work never starves.

Example:
    >>> done = []
    >>> def count(n):
    ...     for i in range(n):
    ...         done.append(i)
    ...         yield
    >>> jobs = Jobs()
    >>> jobs.add(count(3))
    >>> jobs.pump(budget=1.0)
    3
    >>> done, len(jobs)
    ([0, 1, 2], 0)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class Jobs:
    """A queue of generator jobs."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._jobs: list[Iterator[object]] = []

    def __len__(self) -> int:
        return len(self._jobs)

    def add(self, job: Iterator[object]) -> None:
        """Queue `job` behind the others."""
        self._jobs.append(job)

    def cancel(self, job: Iterator[object]) -> None:
        """Drop `job` if it is still queued."""
        if job in self._jobs:
            self._jobs.remove(job)

    def pump(self, budget: float) -> int:
        """Advance jobs for about `budget` seconds and return how many steps ran."""
        deadline = self._clock() + budget
        steps = 0
        while self._jobs:
            job = self._jobs[0]
            try:
                next(job)
            except StopIteration:
                self._jobs.pop(0)
                continue
            steps += 1
            if self._clock() >= deadline:
                break
        return steps
