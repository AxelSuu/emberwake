"""Budget for the software post chain. Timed only by `just bench`; plain test runs call it once."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.render.frame import Flag
from emberwake.engine.render.post import Grade, PostChain

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

SIZE = (320, 180)
BUDGET = 2.5e-3


def test_every_effect_at_canvas_size(benchmark: BenchmarkFixture):
    chain = PostChain(SIZE)
    canvas = pygame.Surface(SIZE)
    flags = Flag.BLOOM | Flag.GRADING | Flag.VIGNETTE | Flag.CRT
    grade = Grade(multiply=(235, 238, 255), add=(0, 0, 4), saturation=0.9)
    benchmark(chain.apply, canvas, flags, grade)
    if benchmark.stats is not None:
        assert benchmark.stats.stats.median < BUDGET
