"""Pause overlay: resume, settings or quit to the title screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pygame

from emberwake.engine.scene import Scene
from emberwake.engine.ui import Button, Label, Panel, UiRoot
from emberwake.game.scenes.settings import SHADE, SettingsScene, load_ui_theme

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


class PauseScene(Scene):
    """Stops the scene below and draws over it. Back resumes."""

    blocks_draw: ClassVar[bool] = False

    def __init__(self, ctx: GameContext, area: str = "", light: str = "") -> None:
        self.ctx = ctx
        where = [Label(text, dim=True) for text in (area, light) if text]
        panel = Panel(
            [
                Label(ctx.t("pause.title")),
                *where,
                Button(ctx.t("pause.resume"), self._resume),
                Button(ctx.t("pause.help"), self._help),
                Button(ctx.t("pause.settings"), self._settings),
                Button(ctx.t("pause.quit"), self._quit),
            ]
        )
        self.ui = UiRoot(panel, load_ui_theme(), self._resume)
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

    def _resume(self) -> None:
        self.manager.pop()

    def _help(self) -> None:
        from emberwake.game.scenes.how_to_play import HowToPlayScene  # noqa: PLC0415

        self.manager.push(HowToPlayScene(self.ctx))

    def _settings(self) -> None:
        self.manager.push(SettingsScene(self.ctx))

    def _quit(self) -> None:
        from emberwake.game.scenes.title import TitleScene  # noqa: PLC0415

        self.manager.switch(TitleScene(self.ctx))
