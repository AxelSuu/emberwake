"""Budgets for hot ECS paths. Timed only by `just bench`; plain test runs call each once."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.ecs import World

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

ENTITIES = 1000
QUERY_BUDGET = 0.3e-3


@dataclass(slots=True)
class Pos:
    x: float = 0.0


@dataclass(slots=True)
class Vel:
    dx: float = 1.0


def test_two_component_query(benchmark: BenchmarkFixture):
    world = World()
    for _ in range(ENTITIES):
        world.spawn(Pos(), Vel())
    world.flush()

    def query() -> int:
        return sum(1 for _ in world.query(Pos, Vel))

    assert benchmark(query) == ENTITIES
    if benchmark.stats is not None:
        assert benchmark.stats.stats.median < QUERY_BUDGET
