from __future__ import annotations

import pygame
import pytest

from emberwake.engine.physics import Body
from emberwake.engine.render.frame import Layer, RenderFrame
from emberwake.game.lamprey import MODES, Lamprey
from emberwake.game.render.lamprey_view import LINKS, LampreyView

STEP = 1 / 60


@pytest.fixture(autouse=True)
def _pygame():
    pygame.init()
    yield
    pygame.quit()


def test_every_mode_draws_the_chain_and_the_head() -> None:
    view = LampreyView()
    body, lamprey = Body(100, 100, 32, 16), Lamprey(arena=(0.0, 0.0, 400.0, 300.0))
    for mode in MODES:
        lamprey.mode = mode
        view.update(body, lamprey, STEP)
        frame = RenderFrame()
        view.queue(frame, body, lamprey, (0, 0), flash=0.5)
        assert len(frame.sprites) == LINKS + 2, mode


def test_the_segments_trail_the_head_with_inertia() -> None:
    view = LampreyView()
    body, lamprey = Body(100, 100, 32, 16), Lamprey()
    view.update(body, lamprey, STEP)
    for _ in range(30):
        body.x += 3
        view.update(body, lamprey, STEP)
    assert view.chain is not None
    tail, head = view.chain.points[-1][0], view.chain.points[0][0]
    assert tail < head - 10


def test_a_jump_of_the_head_does_not_stretch_the_chain() -> None:
    view = LampreyView()
    body, lamprey = Body(100, 100, 32, 16), Lamprey()
    view.update(body, lamprey, STEP)
    body.x += 300
    view.update(body, lamprey, STEP)
    assert view.chain is not None
    assert view.chain.points[-1][0] > body.x - 120


def test_the_pose_follows_the_mode_and_tilts_the_head() -> None:
    view = LampreyView()
    lamprey = Lamprey(mode="stunned", since=0.3, heading=-30.0)
    gape = view.pose(lamprey)
    lamprey.mode = "swim"
    idle = view.pose(lamprey)
    assert gape["jaw"] > 50 > idle["jaw"]
    assert gape["head"] == -30.0


def test_the_water_veil_covers_the_arena_below_the_line_until_it_drains() -> None:
    view = LampreyView()
    body = Body(100, 100, 32, 16)
    lamprey = Lamprey(home=(116.0, 108.0), arena=(0.0, 0.0, 400.0, 300.0))
    frame = RenderFrame()
    view.queue_water(frame, body, lamprey, (10, 20))
    (veil,) = frame.sprites
    assert veil.layer == Layer.FOREGROUND
    assert (veil.x, veil.y) == (-10, 96)
    assert veil.image.get_size() == (400, 300 - 116)
    lamprey.drained = True
    frame = RenderFrame()
    view.queue_water(frame, body, lamprey, (0, 0))
    assert not frame.sprites
