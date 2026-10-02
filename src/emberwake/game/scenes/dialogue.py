"""Conversation and shop overlays."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from emberwake.engine.core.dialogue import DialogueRunner
from emberwake.engine.ui import Button, Label, Panel, UiRoot, Widget
from emberwake.game import paths
from emberwake.game.grants import GIVE, Give, Granted
from emberwake.game.scenes.overlay import Overlay
from emberwake.game.shop import buy, can_buy, load_shops, owned, price, wallet

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.core.dialogue import Graph
    from emberwake.game.context import GameContext
    from emberwake.game.progress import Progress

WRAP = 46
SHOP = "shop:"
PAY = "pay:"


def lines(text: str) -> list[Widget]:
    """`text` as one label per wrapped line."""
    return [Label(line) for line in textwrap.wrap(text, WRAP) or [""]]


class ShopScene(Overlay):
    """Buy from one shop with embers. Each press buys one; back leaves."""

    def __init__(
        self, ctx: GameContext, progress: Progress, save: Callable[[], None], shop: str = "tinker"
    ) -> None:
        self.progress, self.save = progress, save
        self.shop = load_shops(paths.content("shop.toml"))[shop]
        self.wallet = Label("")
        self.buttons = {
            ident: Button("", lambda ident=ident: self._buy(ident)) for ident in self.shop.items
        }
        back = Button(ctx.t("shop.back"), self._back)
        title = Label(ctx.t(f"shop.title.{shop}"))
        panel = Panel([title, self.wallet, *self.buttons.values(), back])
        super().__init__(ctx, panel, self._back)
        self._refresh()

    def _refresh(self) -> None:
        ctx, save = self.ctx, self.progress.data
        self.wallet.text = ctx.t("shop.wallet", embers=wallet(save))
        for ident, item in self.shop.items.items():
            button = self.buttons[ident]
            name = ctx.t(f"shop.{ident}.name")
            if owned(save, item) >= item.max:
                button.text = ctx.t("shop.sold_out", name=name)
            else:
                button.text = ctx.t("shop.item", name=name, price=price(save, item))
            button.enabled = can_buy(save, item)
        self.ui.center(ctx.canvas_size)

    def _buy(self, ident: str) -> None:
        item = self.shop.items[ident]
        if buy(self.progress.data, item):
            if item.grant:
                self.ctx.bus.publish(Granted(item.grant))
            self.save()
            self._refresh()

    def _back(self) -> None:
        self.manager.pop()


class DialogueScene(Overlay):
    """Shows a conversation line by line; choices are buttons, otherwise accept continues."""

    def __init__(
        self,
        ctx: GameContext,
        graph: Graph,
        progress: Progress,
        save: Callable[[], None],
    ) -> None:
        self.ctx = ctx
        self.progress, self.save = progress, save
        self.runner = DialogueRunner(graph, progress.data.flags)
        super().__init__(ctx, self._panel(), self._leave)
        self._actions()

    def _panel(self) -> Panel:
        ctx, run = self.ctx, self.runner
        rows: list[Widget] = lines(ctx.t(run.text))
        choices = run.choices
        if choices:
            rows.extend(
                Button(ctx.t(choice.text), lambda i=i: self._choose(i))
                for i, choice in enumerate(choices)
            )
        else:
            rows.append(Button(ctx.t("dialogue.continue"), lambda: self._choose(None)))
        return Panel(rows)

    def _choose(self, index: int | None) -> None:
        self.runner.advance(index)
        self.save()
        if self.runner.finished:
            self._leave()
            return
        self.ui = UiRoot(self._panel(), self.ui.theme, self._leave)
        self.ui.center(self.ctx.canvas_size)
        self._actions()

    def _actions(self) -> None:
        for action in self.runner.take_actions():
            if action.startswith(SHOP):
                shop = action.removeprefix(SHOP)
                self.manager.push(ShopScene(self.ctx, self.progress, self.save, shop))
            elif action.startswith(PAY):
                self.progress.data.stats.embers += int(action.removeprefix(PAY))
                self.save()
            elif action.startswith(GIVE):
                self.ctx.bus.publish(Give(action.removeprefix(GIVE)))

    def _leave(self) -> None:
        self.manager.pop()
