"""Cutscenes run on the simulation tick, lock player input and can be skipped with Enter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.cutscene import Script, wait
from emberwake.engine.scene import SceneManager
from emberwake.game.actions import Action
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def test_a_cutscene_runs_with_the_simulation_and_locks_input(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    log: list[str] = []

    def script() -> Script:
        log.append("start")
        yield wait(0.5)
        log.append("end")

    game.cutscenes.play(script())
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert Action.JUMP not in game._sample()
    for _ in range(31):
        scenes.update(STEP)
    assert log == ["start", "end"]
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert Action.JUMP in game._sample()


def test_enter_skips_a_cutscene(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    log: list[str] = []

    def script() -> Script:
        yield wait(99)
        log.append("end")

    game.cutscenes.play(script())
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert not game.cutscenes.active
    assert log == ["end"]
