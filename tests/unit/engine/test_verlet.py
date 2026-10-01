from __future__ import annotations

import itertools
import math

import pytest

from emberwake.engine.render.verlet import Chain

STEP = 1 / 60


def lengths(chain: Chain) -> list[float]:
    pts = chain.points
    return [math.dist(a, b) for a, b in itertools.pairwise(pts)]


def test_a_chain_hangs_from_its_anchor_with_links_kept() -> None:
    chain = Chain((0.0, 0.0), links=4, length=3.0)
    for _ in range(120):
        chain.update((5.0, 5.0), STEP)
    assert chain.points[0] == (5.0, 5.0)
    assert chain.points[-1][1] > 5.0 + 3.0 * 3
    assert lengths(chain) == pytest.approx([3.0] * 4)


def test_moving_the_anchor_leaves_the_tail_behind() -> None:
    chain = Chain((0.0, 0.0), links=4, length=3.0)
    for i in range(10):
        chain.update((i * 4.0, 0.0), STEP)
    assert chain.points[-1][0] < chain.points[0][0] - 3


def test_wind_pushes_the_tail_sideways_and_reset_settles_it() -> None:
    chain = Chain((0.0, 0.0), links=3, length=3.0)
    chain.wind = -500.0
    for _ in range(60):
        chain.update((0.0, 0.0), STEP)
    assert chain.points[-1][0] < -2
    chain.reset((10.0, 10.0))
    assert chain.points == [(10.0, 10.0 + i * 3.0) for i in range(4)]
