"""Trials screen: pick a challenge, with your best time and medal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.ui import Button, Label, Panel
from emberwake.game import paths
from emberwake.game.data.records import format_time, load_records
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.overlay import Overlay
from emberwake.game.scenes.results import MEDAL_KEYS
from emberwake.game.trials import listed, load_trials, medal_for, record_key

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


class TrialsScene(Overlay):
    """One button per trial; accept starts it."""

    def __init__(self, ctx: GameContext) -> None:
        self.trials = load_trials(paths.content("trials.toml"))
        stored = load_records(ctx.storage)
        records = stored.runs
        buttons = []
        for ident, trial in self.trials.items():
            if not listed(ident, trial, stored.unlocked):
                continue
            record = records.get(record_key(ident))
            best = format_time(record.best_time) if record else ctx.t("trials.none")
            medal = medal_for(trial, record.best_time) if record else ""
            tag = f"  [{ctx.t(MEDAL_KEYS[medal])}]" if medal else ""
            text = ctx.t("trials.row", name=ctx.t(f"trial.{ident}.name"), best=best, medal=tag)
            buttons.append(Button(text, lambda ident=ident: self._start(ident)))
        self.buttons = buttons
        back = Button(ctx.t("trials.back"), self._back)
        super().__init__(ctx, Panel([Label(ctx.t("trials.title")), *buttons, back]), self._back)

    def _start(self, ident: str) -> None:
        self.manager.switch(GameplayScene(self.ctx, trial=ident))

    def _back(self) -> None:
        self.manager.pop()
