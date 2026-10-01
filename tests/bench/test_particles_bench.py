"""Budgets for the particle system. Timed only by `just bench`; plain test runs call each once."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.render.particles import EmitterSpec, ParticleSystem

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

PARTICLES = 512
UPDATE_BUDGET = 1.0e-3
DRAW_BUDGET = 1.0e-3


def full_system() -> ParticleSystem:
    system = ParticleSystem(PARTICLES)
    colors = ["#ffffff", "#fb6b1d", "#b33831"]
    spec = EmitterSpec(count=PARTICLES, life=(100.0, 100.0), gravity=200, drag=0.5, colors=colors)
    system.burst(spec, 0, 0)
    return system


def test_update_full_pool(benchmark: BenchmarkFixture):
    system = full_system()
    benchmark(system.update, 1 / 60)
    assert system.count == PARTICLES
    if benchmark.stats is not None:
        assert benchmark.stats.stats.median < UPDATE_BUDGET


def test_draw_full_pool(benchmark: BenchmarkFixture):
    system = full_system()
    canvas = pygame.Surface((320, 180))
    benchmark(system.draw, canvas, (0, 0))
    if benchmark.stats is not None:
        assert benchmark.stats.stats.median < DRAW_BUDGET
