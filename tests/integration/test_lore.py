"""Lore_Hall: a signpost, an Echo, a Lost Light and a Trial door."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.lore import Sign, speeches
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
ROOM = "Lore_Hall"


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=ROOM)
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def settle(scenes: SceneManager, ticks: int = 3) -> None:
    for _ in range(ticks):
        scenes.update(STEP)


def stand_at(game: GameplayScene, component: type) -> None:
    for _, body, _ in game.world.query(Body, component):
        game.body.x, game.body.y = body.x, body.y + body.height - game.body.height
        return
    raise AssertionError(component)


def said(game: GameplayScene) -> list[str]:
    return [s.text for s in speeches(game.world, game.ctx.t, game.ctx.settings.controls.keys)]


def test_the_signpost_reads_out_the_current_keys_when_near(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    assert said(game) == []
    stand_at(game, Sign)
    settle(scenes)
    (text,) = said(game)
    assert "[Space]" in text
    game.ctx.settings.controls.keys["jump"] = ["j"]
    assert "[J]" in said(game)[0]


def test_the_speech_bubble_is_drawn_over_the_world(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    stand_at(game, Sign)
    settle(scenes)
    canvas = pygame.Surface(ctx.canvas_size)
    game.draw(canvas, 1.0)
    before = pygame.image.tobytes(canvas, "RGB")
    game.bubbles.draw(canvas, "hello", (100, 100))
    assert pygame.image.tobytes(canvas, "RGB") != before
