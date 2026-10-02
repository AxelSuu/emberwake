from __future__ import annotations

import pygame
import pytest

from emberwake.game import palette, paths
from emberwake.game.render.backdrop import (
    FADE,
    Backdrop,
    Backdrops,
    BackdropSpec,
    GradeSpec,
    LayerSpec,
    load_backdrops,
)

SIZE = (64, 36)
RED, BLUE = "#e83b3b", "#4d65b4"
SPECS = {
    "red": BackdropSpec(sky=(RED, RED)),
    "blue": BackdropSpec(
        sky=(BLUE, BLUE),
        layers=[LayerSpec("pillars", 1.5, "#ffffff", top=0, height=36, width=(64, 64))],
    ),
}


def test_every_preset_builds():
    specs = load_backdrops(paths.content("backdrops.toml"))
    assert specs
    for name, spec in specs.items():
        backdrop = Backdrop(name, spec, (640, 360))
        assert len(backdrop.far) + len(backdrop.near) == len(spec.layers)
        assert all(layer.factor > 1 for layer in backdrop.near)


def test_near_layers_are_darkened():
    (near,) = Backdrop("blue", SPECS["blue"], SIZE).near
    assert near.image.get_at((10, 10))[:3] != (255, 255, 255)


def test_cross_fades_between_presets():
    backdrops, canvas = Backdrops(SPECS, SIZE), pygame.Surface(SIZE)
    backdrops.show("red", instantly=True)
    backdrops.draw_far(canvas, (0, 0), 0)
    assert canvas.get_at((1, 1)) == pygame.Color(RED)
    backdrops.show("blue")
    backdrops.update(warm=False, dt=FADE / 2)
    backdrops.draw_far(canvas, (0, 0), 0)
    mixed = canvas.get_at((1, 1))
    assert mixed not in (pygame.Color(RED), pygame.Color(BLUE))
    backdrops.update(warm=False, dt=FADE)
    backdrops.draw_far(canvas, (0, 0), 0)
    assert canvas.get_at((1, 1)) == pygame.Color(BLUE)


def test_warmth_eases_in_and_out():
    backdrops = Backdrops(SPECS, SIZE)
    backdrops.show("blue", instantly=True)
    backdrops.update(warm=True, dt=0.1)
    assert 0 < backdrops.warmth < 1
    backdrops.update(warm=True, dt=10)
    assert backdrops.grade().add[0] > 0
    backdrops.update(warm=False, dt=10)
    assert backdrops.warmth == 0


@pytest.mark.parametrize("name", [None, "nowhere"])
def test_missing_presets_draw_ink(name: str | None):
    backdrops, canvas = Backdrops(SPECS, SIZE), pygame.Surface(SIZE)
    backdrops.show(name, instantly=True)
    backdrops.draw_far(canvas, (0, 0), 0)
    backdrops.draw_near(canvas, (0, 0), 0)
    assert canvas.get_at((1, 1)) == pygame.Color(palette.INK)


def test_grade_cross_fades_and_warms():
    specs = {
        "a": BackdropSpec(grade=GradeSpec(multiply=(100, 100, 100))),
        "b": BackdropSpec(grade=GradeSpec(multiply=(200, 200, 200))),
    }
    backdrops = Backdrops(specs, SIZE)
    backdrops.show("a", instantly=True)
    assert backdrops.grade().multiply == (100, 100, 100)
    backdrops.show("b")
    backdrops.update(warm=False, dt=FADE / 2)
    assert backdrops.grade().multiply == (150, 150, 150)
    backdrops.update(warm=False, dt=FADE)
    assert backdrops.grade().multiply == (200, 200, 200)


def test_ambient_cross_fades_and_brightens_with_a_lit_beacon():
    specs = {
        "a": BackdropSpec(ambient=(40, 40, 40), ambient_lit=(200, 200, 200)),
        "b": BackdropSpec(ambient=(80, 80, 80), ambient_lit=(240, 240, 240)),
    }
    backdrops = Backdrops(specs, SIZE)
    backdrops.show("a", instantly=True)
    assert backdrops.ambient() == (40, 40, 40)
    backdrops.show("b")
    backdrops.update(warm=False, dt=FADE / 2)
    assert backdrops.ambient() == (60, 60, 60)
    backdrops.update(warm=True, dt=10.0)
    assert backdrops.ambient() == (240, 240, 240)
