"""Small numeric helpers used by movement, cameras and tweens."""

from __future__ import annotations

import math


def approach(value: float, target: float, max_delta: float) -> float:
    """Move `value` toward `target` by at most `max_delta` without overshooting."""
    if value < target:
        return min(value + max_delta, target)
    return max(value - max_delta, target)


def sign(value: float) -> int:
    """``-1``, ``0`` or ``1``."""
    return (value > 0) - (value < 0)


def damp(value: float, target: float, rate: float, dt: float) -> float:
    """Exponential smoothing toward `target` that is independent of the step size.

    `rate` is in 1/s: after ``1 / rate`` seconds about 63% of the distance is covered.
    """
    return target + (value - target) * math.exp(-rate * dt)


def clamp(value: float, low: float, high: float) -> float:
    """Limit `value` to ``[low, high]``."""
    return max(low, min(value, high))
