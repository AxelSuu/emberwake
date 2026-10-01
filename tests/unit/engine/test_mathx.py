import pytest

from emberwake.engine.core.mathx import approach, clamp, damp, sign


def test_approach_never_overshoots():
    assert approach(0, 10, 3) == 3
    assert approach(9, 10, 3) == 10
    assert approach(10, 0, 4) == 6
    assert approach(1, 0, 4) == 0


def test_sign_and_clamp():
    assert (sign(-2.5), sign(0), sign(7)) == (-1, 0, 1)
    assert (clamp(-1, 0, 5), clamp(3, 0, 5), clamp(9, 0, 5)) == (0, 3, 5)


def test_damp_is_step_size_independent():
    one_step = damp(0, 100, 5, 0.1)
    two_steps = damp(damp(0, 100, 5, 0.05), 100, 5, 0.05)
    assert one_step == pytest.approx(two_steps)
    assert 0 < one_step < 100
