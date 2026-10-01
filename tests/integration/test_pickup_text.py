"""Collecting an ember floats a +N over the player."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.scene import SceneManager
from emberwake.game.interact import Collected
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


def test_collecting_spawns_text_that_expires(ctx: GameContext) -> None:
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.update(1 / 60)
    ctx.bus.publish(Collected("ember", 3))
    assert game.texts.count == 1
    for _ in range(90):
        scenes.update(1 / 60)
    assert game.texts.count == 0
