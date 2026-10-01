from __future__ import annotations

import pygame

from emberwake.engine.render.frame import Flag
from emberwake.engine.render.post import Grade, PostChain

SIZE = (64, 36)
GREY = (100, 100, 100)


def filled(color: tuple[int, int, int] = GREY) -> pygame.Surface:
    surface = pygame.Surface(SIZE)
    surface.fill(color)
    return surface


def test_no_flags_leave_the_canvas_alone():
    canvas = filled()
    PostChain(SIZE).apply(canvas, Flag(0), Grade(multiply=(0, 0, 0)))
    assert canvas.get_at((5, 5))[:3] == GREY


def test_grade_multiplies_adds_and_desaturates():
    chain = PostChain(SIZE)
    canvas = filled((200, 100, 50))
    chain.apply(canvas, Flag.GRADING, Grade(multiply=(128, 255, 255), add=(0, 0, 10)))
    assert canvas.get_at((0, 0))[:3] == (100, 100, 60)
    canvas = filled((200, 100, 50))
    chain.apply(canvas, Flag.GRADING, Grade(saturation=0.0))
    r, g, b = canvas.get_at((0, 0))[:3]
    assert abs(r - g) <= 2
    assert abs(g - b) <= 2


def test_grade_is_skipped_without_its_flag():
    canvas = filled()
    PostChain(SIZE).apply(canvas, Flag(0), Grade(add=(50, 50, 50)))
    assert canvas.get_at((0, 0))[:3] == GREY


def test_vignette_darkens_corners_more_than_the_centre():
    canvas = filled()
    PostChain(SIZE).apply(canvas, Flag.VIGNETTE)
    assert canvas.get_at((0, 0)).r < canvas.get_at((32, 18)).r <= 100


def test_crt_darkens_every_other_row():
    canvas = filled()
    PostChain(SIZE).apply(canvas, Flag.CRT)
    assert canvas.get_at((3, 2)).r == 100
    assert canvas.get_at((3, 3)).r < 100


def test_bloom_spreads_bright_pixels_and_ignores_dim_ones():
    chain = PostChain(SIZE)
    dim = filled((60, 60, 60))
    chain.apply(dim, Flag.BLOOM)
    assert dim.get_at((10, 10))[:3] == (60, 60, 60)
    canvas = filled((0, 0, 0))
    canvas.fill((255, 255, 255), (30, 16, 4, 4))
    chain.apply(canvas, Flag.BLOOM)
    assert canvas.get_at((24, 18)).r > 0
    assert canvas.get_at((0, 0)).r == 0


def test_grade_lerp_blends_and_neutral_is_detected():
    assert Grade().neutral
    mid = Grade().lerp(Grade(multiply=(155, 155, 155), saturation=0.0), 0.5)
    assert mid.multiply == (205, 205, 205)
    assert mid.saturation == 0.5
    assert not mid.neutral
