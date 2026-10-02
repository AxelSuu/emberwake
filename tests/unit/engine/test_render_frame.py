from __future__ import annotations

import pygame
import pytest

from emberwake.engine.render import software
from emberwake.engine.render.frame import Flag, Layer, RenderFrame, ShaftCmd
from emberwake.engine.render.shadows import shadow_mask, visible_outline
from emberwake.engine.render.software import SoftwareBackend

RED, BLUE, BLACK = pygame.Color("red"), pygame.Color("blue"), pygame.Color("black")


def square(color: pygame.Color, size: int = 4) -> pygame.Surface:
    image = pygame.Surface((size, size))
    image.fill(color)
    return image


def canvas() -> pygame.Surface:
    target = pygame.Surface((40, 40))
    target.fill(BLACK)
    return target


def test_sprites_draw_back_to_front_whatever_the_queue_order():
    frame = RenderFrame()
    frame.sprite(square(RED), 10, 10, Layer.FOREGROUND)
    frame.sprite(square(BLUE), 12, 12, Layer.WORLD)
    target = canvas()
    SoftwareBackend().render(frame, target)
    assert target.get_at((13, 13)) == RED
    assert target.get_at((10, 10)) == RED
    assert target.get_at((15, 15)) == BLUE


def test_sprites_land_at_their_rounded_position():
    frame = RenderFrame()
    frame.sprite(square(RED), 4.6, 2.2)
    target = canvas()
    SoftwareBackend().render(frame, target)
    assert target.get_at((5, 2)) == RED
    assert target.get_at((4, 2)) == BLACK


def test_a_light_brightens_the_world_but_not_actors():
    frame = RenderFrame()
    frame.sprite(square(BLUE), 18, 18, Layer.ACTORS)
    frame.sprite(square(BLUE), 2, 2, Layer.WORLD)
    frame.light(20, 20, 16, (255, 128, 0))
    target = canvas()
    SoftwareBackend().render(frame, target)
    assert target.get_at((20, 24)).r > 0
    assert target.get_at((20, 20)) == BLUE
    assert target.get_at((2, 2)) == BLUE


def test_lights_fade_with_intensity_and_vanish_at_zero():
    def lit(intensity: float) -> int:
        frame = RenderFrame()
        frame.light(20, 20, 16, (255, 255, 255), intensity)
        target = canvas()
        SoftwareBackend().render(frame, target)
        return target.get_at((20, 20)).r

    assert lit(0) == 0
    assert 0 < lit(0.5) < lit(1.0)


def test_the_lighting_flag_switches_lights_off():
    frame = RenderFrame(flags=Flag(0))
    frame.light(20, 20, 16, (255, 255, 255))
    target = canvas()
    SoftwareBackend().render(frame, target)
    assert target.get_at((20, 20)) == BLACK


def test_clear_drops_commands_but_keeps_flags():
    frame = RenderFrame(flags=Flag.BLOOM)
    frame.sprite(square(RED), 0, 0)
    frame.light(1, 1, 4, (1, 1, 1))
    frame.clear()
    assert (frame.sprites, frame.lights, frame.flags) == ([], [], Flag.BLOOM)


def wall_at(x: int):
    return lambda px, _py: px >= x


def test_shadows_darken_what_a_wall_hides():
    def lit(flags: Flag) -> tuple[int, int]:
        frame = RenderFrame(flags=flags)
        frame.occluded = wall_at(26)
        frame.light(20, 20, 16, (255, 255, 255))
        target = canvas()
        SoftwareBackend().render(frame, target)
        return target.get_at((21, 20)).r, target.get_at((32, 20)).r

    shadowed = lit(Flag.LIGHTING | Flag.SHADOWS)
    plain = lit(Flag.LIGHTING)
    assert shadowed[0] == pytest.approx(plain[0], abs=3)
    assert plain[1] > 0
    assert shadowed[1] < plain[1] / 2


def test_light_does_not_pass_a_wall_and_a_free_light_is_unmasked():
    assert visible_outline(lambda *_: False, 20, 20, 16) is None
    assert visible_outline(lambda *_: True, 20, 20, 16) is None
    mask = shadow_mask(wall_at(24), 20, 20, 16, canvas())
    assert mask is not None
    assert mask.get_at((16, 16)).r > 200
    assert mask.get_at((30, 16)).r < 60


def test_a_shaft_lights_along_its_angle_and_fades_with_distance():
    def shaft(angle: float, intensity: float = 1.0) -> pygame.Surface:
        frame = RenderFrame(flags=Flag.SHAFTS)
        frame.shaft(ShaftCmd(20, 20, angle, 40, 12, (255, 255, 255), intensity))
        target = pygame.Surface((80, 80))
        target.fill(BLACK)
        SoftwareBackend().render(frame, target)
        return target

    right, down = shaft(0), shaft(90)
    assert right.get_at((45, 20)).r > 0
    assert right.get_at((20, 45)).r == 0
    assert down.get_at((20, 45)).r > 0
    assert right.get_at((28, 20)).r > right.get_at((52, 20)).r
    assert shaft(0, 0.0).get_at((45, 20)).r == 0


def test_shafts_need_their_flag():
    frame = RenderFrame(flags=Flag.LIGHTING)
    frame.shaft(ShaftCmd(20, 20, 0, 40, 12, (255, 255, 255)))
    target = canvas()
    SoftwareBackend().render(frame, target)
    assert target.get_at((30, 20)) == BLACK


def test_in_the_dark_unlit_things_sink_to_the_ambient_and_lit_ones_keep_their_color():
    frame = RenderFrame(ambient=(64, 64, 64))
    white = pygame.Color("white")
    frame.sprite(square(white, 40), 0, 0, Layer.WORLD)
    frame.light(6, 20, 8, (255, 255, 255))
    target = canvas()
    SoftwareBackend().render(frame, target)
    assert target.get_at((36, 20))[:3] == (64, 64, 64)
    assert target.get_at((6, 20)).r > 200


def test_in_the_dark_actors_are_lit_too_and_glow_stays_bright():
    frame = RenderFrame(ambient=(32, 32, 32))
    frame.sprite(square(BLUE), 30, 30, Layer.ACTORS)
    frame.sprite(square(RED), 2, 2, Layer.GLOW)
    target = canvas()
    SoftwareBackend().render(frame, target)
    assert target.get_at((31, 31)).b < 64
    assert target.get_at((3, 3)) == RED


def test_lights_off_screen_are_skipped():
    frame = RenderFrame(ambient=(0, 0, 0))
    frame.light(500, 500, 16, (255, 255, 255))
    frame.light(20, 20, 16, (255, 255, 255))
    assert len(software._visible(frame.lights, canvas().get_rect())) == 1


def test_only_the_biggest_lights_cast_shadows_in_the_dark(monkeypatch: pytest.MonkeyPatch):
    calls: list[int] = []

    def mask(occluded, x, y, radius, like):
        calls.append(radius)

    monkeypatch.setattr(software, "shadow_mask", mask)
    frame = RenderFrame(flags=Flag.LIGHTING | Flag.SHADOWS, ambient=(0, 0, 0))
    frame.occluded = lambda x, y: False
    for i in range(software.SHADOW_BUDGET + 3):
        frame.light(20, 20, 8 + i, (255, 255, 255))
    SoftwareBackend().render(frame, canvas())
    assert len(calls) == software.SHADOW_BUDGET
    assert min(calls) > round(8 * software.REACH) + 2


def test_keyed_lights_cast_shadows_once_until_the_occluders_change(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[int] = []
    real = software.shadow_mask

    def mask(*args):
        calls.append(1)
        return real(*args)

    monkeypatch.setattr(software, "shadow_mask", mask)
    backend = SoftwareBackend()
    frame = RenderFrame(flags=Flag.LIGHTING | Flag.SHADOWS, ambient=(0, 0, 0))
    frame.occluded = lambda x, y: x > 30
    frame.light(20, 20, 16, (255, 255, 255), key="lamp")
    for _ in range(3):
        backend.render(frame, canvas())
    assert len(calls) == 1
    frame.occluder_version += 1
    backend.render(frame, canvas())
    assert len(calls) == 2
