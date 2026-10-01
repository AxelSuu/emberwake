from __future__ import annotations

import itertools

import pygame
import pytest

from emberwake.engine.core.noise import ValueNoise
from emberwake.engine.debug.time_control import TimeControl
from emberwake.engine.render.camera import Camera, CameraTuning
from emberwake.engine.render.shake import Shake

DT = 1 / 60
VIEW = (640, 360)
STILL = CameraTuning(look_ahead=0, vertical_bias=0)


def settle(camera: Camera, x: float, y: float, facing: int = 1, ticks: int = 600) -> None:
    for _ in range(ticks):
        camera.update(x, y, facing, DT)


def test_small_moves_inside_deadzone_do_not_move_camera():
    camera = Camera(VIEW, STILL)
    camera.snap(1000, 500)
    settle(camera, 1000 + STILL.deadzone[0] / 2 - 1, 500)
    assert camera.x == pytest.approx(1000)


def test_follows_target_leaving_deadzone():
    camera = Camera(VIEW, STILL)
    camera.snap(1000, 500)
    settle(camera, 1200, 500)
    assert camera.x == pytest.approx(1200 - STILL.deadzone[0] / 2)


def test_looks_ahead_in_facing_direction():
    camera = Camera(VIEW, CameraTuning(vertical_bias=0))
    camera.snap(1000, 500)
    settle(camera, 1000, 500, facing=-1)
    assert camera.x == pytest.approx(1000 - CameraTuning().look_ahead)


def test_clamped_to_bounds():
    camera = Camera(VIEW, STILL)
    camera.bounds = pygame.Rect(0, 0, 2000, 1000)
    camera.snap(10, 10)
    assert (camera.x, camera.y) == (320, 180)
    assert camera.offset() == (0, 0)
    settle(camera, 5000, 5000)
    assert camera.offset() == pytest.approx((2000 - 640, 1000 - 360), abs=1)


def test_room_smaller_than_view_is_centred():
    camera = Camera(VIEW, STILL)
    camera.bounds = pygame.Rect(100, 100, 300, 200)
    camera.snap(0, 0)
    assert (camera.x, camera.y) == (250, 200)


def test_glide_catches_up_faster_and_ends_when_settled():
    rooms = pygame.Rect(0, 0, 640, 360), pygame.Rect(640, 0, 640, 360)
    gliding, normal = Camera(VIEW, STILL), Camera(VIEW, STILL)
    for camera in (gliding, normal):
        camera.bounds = rooms[0]
        camera.snap(600, 180)
    gliding.glide_to(rooms[1])
    normal.bounds = rooms[1]
    for _ in range(10):
        gliding.update(700, 180, 1, DT)
        normal.update(700, 180, 1, DT)
    assert gliding.x > normal.x
    settle(gliding, 700, 180)
    assert not gliding.gliding
    assert gliding.x == pytest.approx(960)


def test_offset_interpolates_between_ticks():
    camera = Camera(VIEW, STILL)
    camera.snap(1000, 500)
    camera.update(1300, 500, 1, DT)
    start, end = camera.offset(0.0), camera.offset(1.0)
    middle = camera.offset(0.5)
    assert start[0] < middle[0] < end[0]


def test_shake_is_zero_without_trauma_and_decays():
    shake = Shake()
    assert shake.offset == (0, 0)
    shake.add(1.0)
    shake.update(DT)
    assert shake.offset != (0, 0)
    for _ in range(120):
        shake.update(DT)
    assert shake.trauma == 0
    assert shake.offset == (0, 0)


def test_shake_respects_intensity_and_is_deterministic():
    a, b = Shake(seed=3), Shake(seed=3)
    for shake in (a, b):
        shake.add(0.8)
        shake.update(DT)
    assert a.offset == b.offset
    a.intensity = 0
    assert a.offset == (0, 0)


def test_value_noise_is_smooth_and_bounded():
    noise = ValueNoise(5)
    values = [noise(i / 10) for i in range(2000)]
    assert all(-1 <= v <= 1 for v in values)
    assert max(abs(a - b) for a, b in itertools.pairwise(values)) < 0.4


def test_time_control():
    time = TimeControl(slow_factor=3)
    assert time.should_tick()
    time.toggle_pause()
    assert not time.should_tick()
    time.step()
    assert time.should_tick()
    assert not time.should_tick()
    time.toggle_pause()
    time.toggle_slow()
    assert [time.should_tick() for _ in range(6)] == [False, False, True, False, False, True]
