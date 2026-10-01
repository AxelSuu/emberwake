"""Deterministic smooth noise for shakes, flickers and wobbles."""

from __future__ import annotations

import math
import random

TABLE_SIZE = 256


class ValueNoise:
    """1D value noise in ``[-1, 1]``: smooth, repeatable for a seed, period 256.

    Example:
        >>> noise = ValueNoise(seed=1)
        >>> noise(0.5) == ValueNoise(seed=1)(0.5)
        True
    """

    def __init__(self, seed: int = 0) -> None:
        rng = random.Random(seed)
        self._table = [rng.uniform(-1.0, 1.0) for _ in range(TABLE_SIZE)]

    def __call__(self, x: float) -> float:
        """Noise value at `x`; integer steps are one random lattice point apart."""
        i = math.floor(x)
        f = x - i
        t = f * f * (3 - 2 * f)
        a = self._table[i % TABLE_SIZE]
        b = self._table[(i + 1) % TABLE_SIZE]
        return a + (b - a) * t
