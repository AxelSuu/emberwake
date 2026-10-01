from __future__ import annotations

import pygame
import pytest

from emberwake.engine.render.floating_text import FloatingTexts, ease_out
from emberwake.engine.render.hit_flash import HitFlash, flashed


@pytest.fixture(autouse=True)
def fonts() -> None:
    pygame.font.init()


def canvas() -> pygame.Surface:
    surface = pygame.Surface((64, 64), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 255))
    return surface


def lit(surface: pygame.Surface) -> int:
    return sum(surface.get_at((x, y)).r > 0 for x in range(64) for y in range(64))


def test_ease_out_runs_from_zero_to_one() -> None:
    assert ease_out(0) == 0
    assert ease_out(1) == 1
    assert ease_out(0.5) > 0.5


def test_text_rises_and_expires() -> None:
    texts = FloatingTexts()
    texts.spawn("5", 32, 40, rise=20, life=1.0)
    start, end = canvas(), canvas()
    texts.draw(start, (0, 0))
    texts.update(0.4)
    texts.draw(end, (0, 0))
    top = lambda s: min(y for y in range(64) for x in range(64) if s.get_at((x, y)).r > 0)  # noqa: E731
    assert top(end) < top(start)
    texts.update(0.7)
    assert texts.count == 0


def test_text_fades_out() -> None:
    texts = FloatingTexts()
    texts.spawn("W", 32, 32, life=1.0)
    early, late = canvas(), canvas()
    texts.update(0.1)
    texts.draw(early, (0, 0))
    texts.update(0.8)
    texts.draw(late, (0, 0))
    assert max(early.get_at((x, y)).r for x in range(64) for y in range(64)) > max(
        late.get_at((x, y)).r for x in range(64) for y in range(64)
    )


def test_pool_is_capped_and_reuses_slots() -> None:
    texts = FloatingTexts(capacity=2)
    for _ in range(5):
        texts.spawn("1", 0, 0, life=0.1)
    assert (texts.count, texts.dropped) == (2, 3)
    texts.update(0.2)
    assert texts.count == 0
    texts.spawn("2", 0, 0)
    assert texts.count == 1


def test_camera_offset_moves_the_text() -> None:
    texts = FloatingTexts()
    texts.spawn("X", 100, 100, rise=0)
    shown = canvas()
    texts.draw(shown, (80, 80))
    assert lit(shown) > 0
    hidden = canvas()
    texts.draw(hidden, (0, 0))
    assert lit(hidden) == 0


def test_hit_flash_timer() -> None:
    flash = HitFlash(0.1)
    assert flash.amount == 0
    flash.start()
    assert flash.amount == 1
    flash.update(0.05)
    assert flash.amount == pytest.approx(0.5)
    flash.update(1)
    assert flash.amount == 0


def test_muted_hit_flash_never_starts() -> None:
    flash = HitFlash()
    flash.muted = True
    flash.start()
    assert flash.amount == 0


def test_flashed_whitens_opaque_pixels_only() -> None:
    sprite = pygame.Surface((4, 4), pygame.SRCALPHA)
    sprite.fill((0, 0, 0, 0))
    sprite.set_at((1, 1), (200, 40, 40, 255))
    assert flashed(sprite, 0) is sprite
    full = flashed(sprite, 1)
    assert tuple(full.get_at((1, 1))) == (255, 255, 255, 255)
    assert full.get_at((0, 0)).a == 0
    half = flashed(sprite, 0.5).get_at((1, 1))
    assert 200 < half.r < 255
    assert half.g > 40
    assert tuple(sprite.get_at((1, 1))) == (200, 40, 40, 255)
