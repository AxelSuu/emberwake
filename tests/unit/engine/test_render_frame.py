from __future__ import annotations

import pygame

from emberwake.engine.render.frame import Flag, Layer, RenderFrame
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
