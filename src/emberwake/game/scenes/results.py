"""Results screen: the run's stats against the stored best."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import pygame

from emberwake.engine.scene import Scene
from emberwake.engine.ui import Button, Label, Panel, UiRoot
from emberwake.game.data.records import (
    RunResult,
    format_time,
    load_records,
    save_records,
    submit,
)
from emberwake.game.scenes.settings import SHADE, load_ui_theme

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


MEDAL_KEYS = {"gold": "medal.gold", "silver": "medal.silver", "bronze": "medal.bronze"}


@dataclass(frozen=True, slots=True)
class RunFinished:
    """Published when a run (a trial, a finished game) ends; the gameplay scene shows results."""

    result: RunResult


class ResultsScene(Scene):
    """Records `result` on entry, shows it and closes on accept or back."""

    blocks_draw: ClassVar[bool] = False

    def __init__(self, ctx: GameContext, result: RunResult) -> None:
        self.ctx = ctx
        self.result = result
        records = load_records(ctx.storage)
        self.new_best = submit(records, result)
        save_records(ctx.storage, records)
        best = records.runs[result.key].best_time
        t = ctx.t
        rows = [
            Label(t("results.title")),
            Label(t("results.time", time=format_time(result.time))),
            Label(t("results.best", time=format_time(best))),
            Label(t("results.deaths", count=result.deaths), dim=True),
            Label(t("results.embers", count=result.embers), dim=True),
        ]
        if result.medal:
            rows.insert(1, Label(t("results.medal", medal=t(MEDAL_KEYS[result.medal]))))
        if self.new_best:
            rows.insert(1, Label(t("results.new_best")))
        rows.append(Button(t("results.continue"), self._close))
        self.ui = UiRoot(Panel(rows), load_ui_theme(), self._close)
        self.ui.center(ctx.canvas_size)

    def handle(self, event: pygame.Event) -> None:
        self.ui.handle(event)

    def update(self, dt: float) -> None:
        self.ui.update(dt)

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        shade = pygame.Surface(canvas.get_size())
        shade.set_alpha(SHADE)
        canvas.blit(shade, (0, 0))
        self.ui.draw(canvas)

    def _close(self) -> None:
        self.manager.pop()
