"""Budget for shadowed lights. Timed only by `just bench`; plain test runs call it once."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.render.frame import Flag, RenderFrame
from emberwake.engine.render.software import SoftwareBackend

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

BUDGET = 3e-3
LIGHTS = 4


def test_four_shadowed_lights_in_a_cave(benchmark: BenchmarkFixture):
    backend, canvas = SoftwareBackend(), pygame.Surface((320, 180))
    frame = RenderFrame(flags=Flag.LIGHTING | Flag.SHADOWS)
    frame.occluded = lambda x, y: int(x) % 40 < 8 or y > 140
    for i in range(LIGHTS):
        frame.light(40 + i * 70, 100, 64, (251, 107, 29), 0.8)
    benchmark(backend.render, frame, canvas)
    if benchmark.stats is not None:
        assert benchmark.stats.stats.median < BUDGET


DARK_BUDGET = 4e-3


def test_a_dark_room_with_a_dozen_lamps(benchmark: BenchmarkFixture):
    """Lamps stand still, so their shadows are cast once; the cost is the light map."""
    backend, canvas = SoftwareBackend(), pygame.Surface((640, 360))
    frame = RenderFrame(flags=Flag.LIGHTING | Flag.SHADOWS, ambient=(78, 68, 102))
    frame.occluded = lambda x, y: int(x) % 80 < 10 or y > 300
    for i in range(12):
        frame.light(30 + i * 52, 120 + (i % 3) * 60, 72, (251, 107, 29), 0.8, key=i)
    benchmark(backend.render, frame, canvas)
    if benchmark.stats is not None:
        assert benchmark.stats.stats.median < DARK_BUDGET
