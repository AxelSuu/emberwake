"""Trials: a bot can finish both, medals and records are kept, and the ghost races the next run."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Tile
from emberwake.engine.scene import SceneManager
from emberwake.game.actions import Action
from emberwake.game.data.records import load_records
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.menu import MenuScene
from emberwake.game.scenes.results import ResultsScene
from emberwake.game.scenes.title import TitleScene
from emberwake.game.scenes.trials import TrialsScene
from emberwake.game.trials import ghost_key, load_ghost, medal_for, record_key

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.game.context import GameContext

STEP = 1 / 60
AHEAD = 2


def bot(game: GameplayScene):
    """Run right, and jump when the ground ahead ends."""

    def sample() -> frozenset[Action]:
        if game.trial_done:
            return frozenset()
        body, motor = game.body, game.motor
        size = game.grid.tile_size
        column = int((body.x + body.width + AHEAD) // size)
        row = int((body.y + body.height + 1) // size)
        ground_ahead = game.grid.get(column, row) is Tile.SOLID
        if motor.grounded and not ground_ahead:
            return frozenset({Action.RIGHT, Action.JUMP})
        return frozenset({Action.RIGHT})

    return sample


def drive(game: GameplayScene, sample: Callable[[], frozenset[Action]]) -> None:
    """Replace the game's input with `sample`, as a player would."""
    game.__dict__["_sample"] = sample


def run_trial(ctx: GameContext, name: str, seconds: float = 20.0) -> GameplayScene:
    scenes = SceneManager()
    game = GameplayScene(ctx, trial=name)
    drive(game, bot(game))
    scenes.push(game)
    for _ in range(round(seconds / STEP)):
        scenes.update(STEP)
        if game.trial_done:
            break
    return game


def test_a_bot_finishes_the_sprint_with_a_medal(ctx: GameContext) -> None:
    game = run_trial(ctx, "sprint")
    assert game.trial_done
    assert game.trial is not None
    assert medal_for(game.trial, game.trial_time) == "gold"


def test_a_bot_finishes_the_pits(ctx: GameContext) -> None:
    game = run_trial(ctx, "pits")
    assert game.trial_done
    assert game.trial is not None
    assert game.trial_time < game.trial.bronze


def test_the_results_screen_shows_the_medal_and_records_the_time(ctx: GameContext) -> None:
    scenes = SceneManager()
    game = GameplayScene(ctx, trial="sprint")
    drive(game, bot(game))
    scenes.push(game)
    for _ in range(round(20 / STEP)):
        scenes.update(STEP)
        if isinstance(scenes.top, ResultsScene):
            break
    results = scenes.top
    assert isinstance(results, ResultsScene)
    assert results.result.medal
    assert results.new_best
    assert load_records(ctx.storage).runs[record_key("sprint")].best_time == results.result.time
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    scenes.update(STEP)
    scenes.update(STEP)
    assert isinstance(scenes.top, TitleScene)


def test_a_new_best_saves_a_ghost_that_races_the_next_attempt(ctx: GameContext) -> None:
    first = run_trial(ctx, "sprint")
    assert first.trial_done
    scenes = SceneManager()
    scenes.push(first)
    for _ in range(3):
        scenes.update(STEP)
    assert ctx.storage.read(ghost_key("sprint")) is not None
    ghost = load_ghost(ctx.storage, "sprint")
    assert ghost is not None
    assert ghost.ticks > 60

    second = GameplayScene(ctx, trial="sprint")
    assert second.ghost is not None
    start = second.ghost.body.x
    drive(second, bot(second))
    scene2 = SceneManager()
    scene2.push(second)
    for _ in range(90):
        scene2.update(STEP)
    assert second.ghost.body.x > start + 50
    assert abs(second.ghost.body.x - second.body.x) < 4


def test_a_slower_run_does_not_replace_the_ghost(ctx: GameContext) -> None:
    run_trial(ctx, "sprint")
    before = ctx.storage.read(ghost_key("sprint"))
    scenes = SceneManager()
    game = GameplayScene(ctx, trial="sprint")
    sample = bot(game)
    drive(game, lambda: frozenset() if game.trial_time < 3.0 else sample())
    scenes.push(game)
    for _ in range(round(25 / STEP)):
        scenes.update(STEP)
        if game.trial_done:
            break
    assert game.trial_done
    assert ctx.storage.read(ghost_key("sprint")) == before


def test_dying_restarts_the_attempt_but_not_the_clock(ctx: GameContext) -> None:
    scenes = SceneManager()
    game = GameplayScene(ctx, trial="pits")
    scenes.push(game)
    scenes.update(STEP)
    game.body.y += 400
    for _ in range(60):
        scenes.update(STEP)
    assert game.trial_deaths >= 1
    assert game.trial_time > 0.5
    assert not game.motor.dead


def test_the_menu_lists_trials_and_starts_one(ctx: GameContext) -> None:
    scenes = SceneManager()
    scenes.push(TitleScene(ctx))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    scenes.update(STEP)
    menu = scenes.top
    assert isinstance(menu, MenuScene)
    for _ in range(8):
        current = menu.ui.root.current
        if current is not None and current.text == "Trials":
            break
        scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    scenes.update(STEP)
    trials = scenes.top
    assert isinstance(trials, TrialsScene)
    assert next(b.text for b in trials.buttons).startswith("Sprint")
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    scenes.update(STEP)
    assert isinstance(scenes.top, GameplayScene)
    assert scenes.top.trial_id == "sprint"
