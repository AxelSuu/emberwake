"""How to play: every action with its current keys, and tips that name those keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.ui import Button, Label, Panel, Row, ScrollList, Widget
from emberwake.game.actions import Action
from emberwake.game.scenes.controls import LABELS
from emberwake.game.scenes.overlay import Overlay

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

VISIBLE_ROWS = 12
KEYS_SHOWN = 3
TIPS = (
    "help.tip.move",
    "help.tip.wall",
    "help.tip.drop",
    "help.tip.dash",
    "help.tip.swing",
    "help.tip.interact",
    "help.tip.flare",
    "help.tip.ember",
    "help.tip.kindle",
    "help.tip.beacon",
    "help.tip.hazard",
)
"""In the order a new player meets them. Placeholders are action names, filled with keys."""


def key_name(name: str) -> str:
    """A pygame key name as players read it: "left shift" -> "Left Shift", "e" -> "E"."""
    return name.title()


def keys_text(keys: dict[str, list[str]], action: Action) -> str:
    """Up to three of the keys bound to `action`, or a dash if none."""
    names = [key_name(name) for name in keys.get(action, [])[:KEYS_SHOWN]]
    return " / ".join(names) or "-"


class HowToPlayScene(Overlay):
    """A scrolling list of controls, then tips; rebinding shows up here immediately."""

    def __init__(self, ctx: GameContext) -> None:
        self.rows = self._rows(ctx)
        list_ = ScrollList(self.rows, VISIBLE_ROWS)
        back = Button(ctx.t("help.back"), self._back)
        super().__init__(ctx, Panel([Label(ctx.t("help.title")), list_, back]), self._back)

    @staticmethod
    def _rows(ctx: GameContext) -> list[Widget]:
        keys = ctx.settings.controls.keys
        first = {action.value: key_name(next(iter(keys.get(action, [])), "-")) for action in Action}
        rows: list[Widget] = [Label(ctx.t("help.controls"), dim=True)]
        rows.extend(Row(ctx.t(LABELS[action]), keys_text(keys, action)) for action in Action)
        rows.append(Label(ctx.t("help.tips"), dim=True))
        rows.extend(Row(ctx.t(tip, **first)) for tip in TIPS)
        return rows

    def _back(self) -> None:
        self.manager.pop()
