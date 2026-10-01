from __future__ import annotations

import math

import pytest

from emberwake.engine.render.ik import Gait, Leg, forward, knee, two_bone
from emberwake.engine.render.rig import Bone, Rig


@pytest.mark.parametrize("target", [(10, 20), (-12, 15), (0, 24), (18, 0), (-5, -10), (3, 3)])
@pytest.mark.parametrize("bend", [1, -1])
def test_the_foot_lands_on_a_reachable_target(target: tuple[float, float], bend: int) -> None:
    a1, a2, reached = two_bone((0, 0), target, 12, 12, bend=bend)
    assert reached
    x, y = forward((0, 0), 12, 12, (a1, a2))
    assert (x, y) == pytest.approx(target, abs=1e-6)


def test_the_knee_bulges_to_the_chosen_side() -> None:
    down = (0, 20)
    for bend in (1, -1):
        a1, _, _ = two_bone((0, 0), down, 12, 12, bend=bend)
        kx, _ = knee((0, 0), 12, a1)
        assert (kx > 0) == (bend > 0)


def test_unequal_bones_still_reach() -> None:
    a1, a2, reached = two_bone((5, 5), (20, 25), 10, 18)
    assert reached
    assert forward((5, 5), 10, 18, (a1, a2)) == pytest.approx((20, 25), abs=1e-6)


def test_out_of_reach_stretches_straight_toward_the_target() -> None:
    a1, a2, reached = two_bone((0, 0), (100, 0), 12, 12)
    assert not reached
    assert a1 == pytest.approx(0, abs=1e-3)
    assert abs(a2) < 1e-2
    x, _ = forward((0, 0), 12, 12, (a1, a2))
    assert x == pytest.approx(24, abs=1e-3)


def test_too_close_folds_and_a_zero_distance_does_not_crash() -> None:
    _, _, reached = two_bone((0, 0), (1, 0), 12, 20)
    assert not reached
    two_bone((0, 0), (0, 0), 12, 12)


def test_angles_drive_a_rig_to_the_same_foot() -> None:
    a1, a2, _ = two_bone((10, 10), (20, 30), 12, 14)
    rig = Rig(
        [
            Bone("hip", offset=(10, 10)),
            Bone("knee", "hip", offset=(12, 0)),
            Bone("foot", "knee", offset=(14, 0)),
        ]
    )
    t = rig.solve({"hip": a1, "knee": a2})
    assert (t["foot"].x, t["foot"].y) == pytest.approx((20, 30), abs=1e-6)


def flat(_: float) -> float:
    return 100.0


def test_a_leg_plants_where_it_first_stands() -> None:
    leg = Leg(hip=(0, 80), reach=(0, 20))
    gait = Gait([leg])
    gait.update((50, 0), 0, flat, 0.016)
    assert leg.foot == pytest.approx((50, 100))


def test_a_planted_foot_stays_put_for_small_moves() -> None:
    leg = Leg(hip=(0, 80), step_distance=10)
    gait = Gait([leg])
    gait.update((50, 0), 0, flat, 0.016)
    planted = leg.foot
    for i in range(1, 6):
        gait.update((50 + i, 0), 0, flat, 0.016)
    assert leg.foot == planted
    assert not leg.stepping


def test_a_far_body_makes_the_leg_step_with_a_lifted_arc() -> None:
    leg = Leg(hip=(0, 80), step_distance=10, step_time=0.4, lift=6)
    gait = Gait([leg])
    gait.update((50, 0), 0, flat, 0.016)
    start = leg.foot
    gait.update((70, 0), 0, flat, 0.016)
    assert leg.stepping
    gait.update((70, 0), 0, flat, 0.2)
    assert leg.foot is not None
    assert leg.foot[1] < 100 - 3
    assert start is not None
    assert start[0] < leg.foot[0]
    gait.update((70, 0), 0, flat, 0.5)
    assert not leg.stepping
    assert leg.foot == pytest.approx((70, 100))


def test_the_gait_keeps_feet_down() -> None:
    legs = [Leg(hip=(x, 80), step_distance=6, step_time=0.3) for x in (-12, -4, 4, 12)]
    gait = Gait(legs, max_stepping=1)
    most = 0
    for i in range(240):
        gait.update((50 + i * 1.5, 0), 1, flat, 1 / 60)
        most = max(most, sum(leg.stepping for leg in legs))
    assert most == 1
    assert all(leg.foot is not None for leg in legs)


def test_the_most_lagging_leg_steps_first() -> None:
    near = Leg(hip=(0, 80), step_distance=4)
    far = Leg(hip=(20, 80), step_distance=4)
    gait = Gait([near, far], max_stepping=1)
    gait.update((50, 0), 0, flat, 0.016)
    near.foot = (50, 100)
    far.foot = (30, 100)
    gait.update((50, 0), 0, flat, 0.016)
    assert far.stepping
    assert not near.stepping


def test_feet_follow_uneven_ground() -> None:
    def slope(x: float) -> float:
        return 100.0 + x * 0.2

    leg = Leg(hip=(0, 60), step_distance=5, reach=(0, 30), upper=40, lower=40)
    gait = Gait([leg])
    gait.update((0, 0), 1, slope, 0.016)
    for i in range(1, 120):
        gait.update((i * 1.0, 0), 1, slope, 1 / 60)
    assert leg.foot is not None
    assert leg.foot[1] > 100 + 0.2 * 20


def test_angles_reach_the_planted_foot() -> None:
    leg = Leg(hip=(0, 10), upper=14, lower=14, reach=(0, 20))
    Gait([leg]).update((0, 0), 0, lambda x: 30.0, 0.016)
    a1, a2, reached = leg.angles((0, 0))
    assert reached
    assert forward((0, 10), 14, 14, (a1, a2)) == pytest.approx(leg.foot, abs=1e-6)
    assert math.isfinite(a1)
