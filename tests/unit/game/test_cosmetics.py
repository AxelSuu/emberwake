from __future__ import annotations

import pygame
from tests.unit.game.test_strings import TABLES

from emberwake.engine.debug.time_control import TimeControl
from emberwake.game import paths
from emberwake.game.cosmetics import Cosmetics, Skin, load_cosmetics
from emberwake.game.render.placeholder import PlayerSprite

COSMETICS = load_cosmetics(paths.content("cosmetics.toml"))


def test_shipped_cosmetics_load_with_defaults() -> None:
    assert "default" in COSMETICS.skins
    assert "ember" in COSMETICS.lanterns
    assert len(COSMETICS.skins) > 1
    assert len(COSMETICS.lanterns) > 1


def test_every_skin_and_lantern_has_a_name_in_every_language() -> None:
    for language, table in TABLES.items():
        for name in COSMETICS.skins:
            assert table[f"skin.{name}"], (language, name)
        for name in COSMETICS.lanterns:
            assert table[f"lantern.{name}"], (language, name)


def test_unknown_names_fall_back() -> None:
    assert COSMETICS.skin("nope") == COSMETICS.skins["default"]
    assert COSMETICS.lantern("nope", "#ffffff") == COSMETICS.lanterns["ember"]
    empty = Cosmetics()
    assert empty.skin("x") == Skin()
    assert empty.lantern("x", "#123456") == "#123456"


def test_a_skin_recolors_the_cloak_only() -> None:
    pygame.init()
    pygame.display.set_mode((8, 8))
    plain = PlayerSprite().image(1, 1.0, 1.0)
    dusk = PlayerSprite({"cloak": "#4d9be6"}).image(1, 1.0, 1.0)
    assert plain.get_size() == dusk.get_size()
    assert tuple(plain.get_at((4, 18))) != tuple(dusk.get_at((4, 18)))
    assert tuple(plain.get_at((12, 12))) == tuple(dusk.get_at((12, 12)))


def test_the_lantern_color_changes_the_flame() -> None:
    pygame.init()
    pygame.display.set_mode((8, 8))
    ember = PlayerSprite().image(1, 1.0, 1.0)
    mint = PlayerSprite(None, "#30e1b9").image(1, 1.0, 1.0)
    assert tuple(ember.get_at((11, 12))) != tuple(mint.get_at((11, 12)))
    assert tuple(mint.get_at((11, 12)))[:3] == (0x30, 0xE1, 0xB9)


def test_reduced_game_speed_runs_a_fraction_of_the_ticks() -> None:
    control = TimeControl()
    control.speed = 0.5
    assert sum(control.should_tick() for _ in range(100)) == 50
    control.speed = 0.75
    assert sum(control.should_tick() for _ in range(100)) == 75
    control.speed = 1.0
    assert all(control.should_tick() for _ in range(10))


def test_pause_and_slow_motion_still_win_over_speed() -> None:
    control = TimeControl()
    control.paused = True
    assert not control.should_tick()
    control.paused = False
    control.slow = True
    assert sum(control.should_tick() for _ in range(100)) == 25
