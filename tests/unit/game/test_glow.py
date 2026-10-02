from __future__ import annotations

import pygame

from emberwake.game import palette
from emberwake.game.render.glow import Glows, glow_of


def test_only_emissive_pixels_glow() -> None:
    image = pygame.Surface((3, 1), pygame.SRCALPHA)
    image.set_at((0, 0), palette.INK)
    image.set_at((1, 0), palette.EMBER_HOT)
    image.set_at((2, 0), "#8ff8e2")
    glow = glow_of(image)
    assert glow is not None
    assert glow.get_at((0, 0)).a == 0
    assert glow.get_at((1, 0)) == pygame.Color(palette.EMBER_HOT)
    assert glow.get_at((2, 0)) == pygame.Color("#8ff8e2")


def test_nothing_to_glow_is_none_and_results_are_cached() -> None:
    dull = pygame.Surface((2, 2), pygame.SRCALPHA)
    dull.fill(palette.PLUM)
    glows = Glows()
    assert glows(dull) is None
    assert glows(dull) is None
    assert len(glows._cache) == 1
