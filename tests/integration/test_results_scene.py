"""A finished run opens the results screen and updates records.json."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import SceneManager
from emberwake.game.data.records import RunResult, load_records
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.results import ResultsScene, RunFinished

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


def finish(ctx: GameContext, time: float) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.update(1 / 60)
    ctx.bus.publish(RunFinished(RunResult("trial/ascent", time, deaths=1, embers=5)))
    scenes.update(1 / 60)
    return scenes, game


def test_finishing_a_run_shows_results_and_saves_the_record(ctx: GameContext) -> None:
    scenes, _ = finish(ctx, 75.0)
    assert isinstance(scenes.top, ResultsScene)
    assert scenes.top.new_best
    assert load_records(ctx.storage).runs["trial/ascent"].best_time == 75.0


def test_a_slower_run_is_not_a_best(ctx: GameContext) -> None:
    finish(ctx, 60.0)
    scenes, _ = finish(ctx, 90.0)
    assert isinstance(scenes.top, ResultsScene)
    assert not scenes.top.new_best
    assert load_records(ctx.storage).runs["trial/ascent"].best_time == 60.0


def test_accept_returns_to_gameplay(ctx: GameContext) -> None:
    scenes, game = finish(ctx, 75.0)
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    scenes.update(1 / 60)
    assert scenes.top is game
