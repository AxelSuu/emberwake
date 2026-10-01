from __future__ import annotations

import pygame
import pytest

from emberwake.game import palette
from emberwake.game.render.hud import BANNER_SHOWN, EMBERS_SHOWN, ORIGIN, Hud, HudState


@pytest.fixture(autouse=True)
def fonts():
    pygame.font.init()


def state(**changes: object) -> HudState:
    values: dict[str, object] = {
        "health": 2,
        "max_health": 3,
        "flame": 50.0,
        "max_flame": 100.0,
        "flares": 1,
        "max_flares": 2,
        "embers": 5,
    }
    return HudState(**{**values, **changes})  # ty: ignore[invalid-argument-type]


def canvas() -> pygame.Surface:
    surface = pygame.Surface((320, 180))
    surface.fill(palette.PLUM)
    return surface


def test_full_pips_glow_and_empty_ones_do_not() -> None:
    target = canvas()
    Hud().draw(target, state(health=1, max_health=2))
    x, y = ORIGIN
    assert target.get_at((x + 2, y + 4)) == pygame.Color(palette.EMBER_HOT)
    assert target.get_at((x + 2 + 9, y + 4)) == pygame.Color(palette.NIGHT)


def test_the_ember_count_shows_only_after_it_changes() -> None:
    hud = Hud()
    hud.draw(canvas(), state())
    assert hud.embers_left == 0
    hud.draw(canvas(), state(embers=6))
    assert hud.embers_left == EMBERS_SHOWN
    hud.update(EMBERS_SHOWN)
    assert hud.embers_left == 0


def test_banners_fade_out_and_hidden_draws_nothing() -> None:
    hud = Hud()
    hud.banner("The Sunken Quarter")
    hud.update(BANNER_SHOWN / 2)
    assert hud.banner_left > 0
    hud.update(BANNER_SHOWN)
    assert hud.banner_left == 0
    hud.hidden = True
    target = canvas()
    hud.draw(target, state())
    assert target.get_at(ORIGIN) == pygame.Color(palette.PLUM)


def test_an_empty_flame_and_no_flares_still_draw() -> None:
    Hud().draw(canvas(), state(flame=0.0, flares=0, max_flares=0))
