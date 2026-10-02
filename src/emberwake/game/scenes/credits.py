"""Credits: a stub list of who made the game, over the game; any key goes back."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.ui import Button, Label, Panel
from emberwake.game.scenes.overlay import Overlay

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

LINES = ("credits.made", "credits.palette", "credits.thanks")


class CreditsScene(Overlay):
    def __init__(self, ctx: GameContext) -> None:
        rows = [Label(ctx.t("credits.title")), *(Label(ctx.t(key), dim=True) for key in LINES)]
        super().__init__(ctx, Panel([*rows, Button(ctx.t("credits.back"), self._back)]), self._back)

    def handle(self, event: pygame.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key not in {pygame.K_UP, pygame.K_DOWN}:
            self._back()
            return
        super().handle(event)

    def _back(self) -> None:
        self.manager.pop()
