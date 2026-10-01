"""A shaded panel over the scene below: the base of the menus and dialogs."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pygame

from emberwake.engine.scene import Scene
from emberwake.engine.ui import Panel, UiRoot
from emberwake.game.scenes.settings import SHADE, load_ui_theme

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.game.context import GameContext


class Overlay(Scene):
    """A panel drawn over the scene below, shaded, with back handled by the panel."""

    blocks_draw: ClassVar[bool] = False

    def __init__(self, ctx: GameContext, panel: Panel, on_back: Callable[[], None]) -> None:
        self.ctx = ctx
        self.ui = UiRoot(panel, load_ui_theme(), on_back)
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
