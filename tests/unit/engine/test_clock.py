import pytest
from hypothesis import given
from hypothesis import strategies as st

from emberwake.engine.core.clock import FixedStep


def test_exact_frames_step_once_each():
    clock = FixedStep(step=1 / 60)
    assert [clock.advance(1 / 60) for _ in range(120)] == [1] * 120


def test_slow_frame_runs_multiple_steps_and_keeps_remainder():
    clock = FixedStep(step=0.01)
    assert clock.advance(0.035) == 3
    assert clock.alpha == pytest.approx(0.5)


def test_long_frames_are_clamped():
    clock = FixedStep(step=0.01, max_frame=0.1)
    assert clock.advance(5.0) == 10


def test_negative_frame_time_is_ignored():
    clock = FixedStep()
    assert clock.advance(-1.0) == 0


@given(st.lists(st.floats(min_value=0, max_value=0.05), max_size=200))
def test_total_steps_track_total_time(frames: list[float]):
    clock = FixedStep(step=1 / 60)
    steps = sum(clock.advance(dt) for dt in frames)
    assert steps == pytest.approx(sum(frames) * 60, abs=1)
    assert 0 <= clock.alpha < 1
