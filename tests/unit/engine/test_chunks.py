from __future__ import annotations

import pygame

from emberwake.engine.render.chunks import ChunkLayer

RED = pygame.Color("red")


def painter(log: list[pygame.Rect]):
    def paint(surface: pygame.Surface, area: pygame.Rect) -> None:
        log.append(area.copy())
        surface.fill(RED)

    return paint


def test_bakes_one_chunk_per_step_including_partial_edges():
    areas: list[pygame.Rect] = []
    layer = ChunkLayer((0, 0), (300, 100), painter(areas), chunk=256)
    steps = layer.bake()
    assert layer.total == 2
    next(steps)
    assert (layer.baked, areas) == (1, [pygame.Rect(0, 0, 256, 100)])
    next(steps)
    assert areas[1] == pygame.Rect(256, 0, 44, 100)
    assert list(steps) == []


def test_draw_bakes_only_visible_chunks_at_world_offset():
    areas: list[pygame.Rect] = []
    layer = ChunkLayer((1000, 0), (1024, 256), painter(areas), chunk=256)
    target = pygame.Surface((100, 50))
    layer.draw(target, (1000 + 300, 10))
    assert areas == [pygame.Rect(256, 0, 256, 256)]
    assert target.get_at((0, 0)) == RED
    layer.draw(target, (0, 0))
    assert layer.baked == 1


def test_draw_across_a_chunk_seam_and_skip_baked_steps():
    areas: list[pygame.Rect] = []
    layer = ChunkLayer((0, 0), (512, 512), painter(areas), chunk=256)
    layer.draw(pygame.Surface((40, 40)), (236, 236))
    assert len(areas) == 4
    assert list(layer.bake()) == []
