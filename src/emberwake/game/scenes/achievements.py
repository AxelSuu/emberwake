"""Achievements screen: what is unlocked, how far the rest are, and lifetime counters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.ui import Button, Label, Panel, ScrollList, Widget
from emberwake.game.scenes.menu import Overlay

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

VISIBLE_ROWS = 10
COUNTERS = (
    ("achievements.jumps", "Jumped"),
    ("achievements.dashes", "Dashed"),
    ("achievements.deaths", "Died"),
    ("achievements.embers", "Collected"),
)


class AchievementsScene(Overlay):
    """A scrolling list. Rows take focus only so the arrow keys can scroll them."""

    def __init__(self, ctx: GameContext) -> None:
        self.rows = self._rows(ctx)
        list_ = ScrollList(self.rows, VISIBLE_ROWS)
        back = Button(ctx.t("achievements.back"), self._back)
        super().__init__(ctx, Panel([Label(ctx.t("achievements.title")), list_, back]), self._back)

    @staticmethod
    def _rows(ctx: GameContext) -> list[Widget]:
        tracker = ctx.achievements
        rows: list[Widget] = [
            Label(f"{ctx.t(key)}: {tracker.counter(event)}", dim=True) for key, event in COUNTERS
        ]
        for ident in tracker.defs:
            name, desc = ctx.t(f"achievement.{ident}.name"), ctx.t(f"achievement.{ident}.desc")
            current, target = tracker.progress(ident)
            mark = "[x]" if tracker.unlocked(ident) else f"{current}/{target}"
            rows.append(Button(f"{name}: {desc}  {mark}", lambda: None))
        return rows

    def _back(self) -> None:
        self.manager.pop()
