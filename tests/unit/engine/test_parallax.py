from __future__ import annotations

import pygame

from emberwake.engine.render.parallax import ParallaxLayer, wrap_blur

RED, BLUE = pygame.Color("red"), pygame.Color("blue")


def striped(width: int = 20, height: int = 10) -> pygame.Surface:
    image = pygame.Surface((width, height))
    image.fill(RED)
    image.fill(BLUE, (0, 0, 2, height))
    return image


def test_wraps_horizontally_at_its_factor():
    target = pygame.Surface((50, 10))
    layer = ParallaxLayer(striped(), factor=0.5, top=0)
    layer.draw(target, (0, 0), 0)
    assert [target.get_at((x, 0)) for x in (0, 20, 40, 3)] == [BLUE, BLUE, BLUE, RED]
    layer.draw(target, (4, 0), 0)
    assert target.get_at((18, 0)) == BLUE
    assert target.get_at((0, 0)) == RED


def test_scrolls_up_but_never_shows_below_its_bottom():
    target = pygame.Surface((20, 30))
    layer = ParallaxLayer(striped(height=20), factor=1.0, top=15)
    target.fill("black")
    layer.draw(target, (0, 100 + 3), room_top=100)
    assert target.get_at((5, 12)) == RED
    assert target.get_at((5, 11)) == pygame.Color("black")
    target.fill("black")
    layer.draw(target, (0, 100 + 500), room_top=100)
    assert target.get_at((5, 10)) == RED
    assert target.get_at((5, 9)) == pygame.Color("black")


def test_wrap_blur_keeps_size_and_has_no_seam():
    blurred = wrap_blur(striped(), 2)
    assert blurred.get_size() == (20, 10)
    assert blurred.get_at((0, 5)).b > 0
    assert blurred.get_at((19, 5)).b > 0
