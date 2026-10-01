"""Splash shown while the game starts up."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import Scene
from emberwake.game import palette
from emberwake.game.scenes.title import TitleScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

DURATION = 1.6
FADE = 0.4


class BootScene(Scene):
    def __init__(self, ctx: GameContext) -> None:
        self.ctx = ctx
        self.elapsed = 0.0
        self.text = pygame.font.Font(None, 16).render(ctx.t("boot.made_with"), False, palette.MIST)

    def handle(self, event: pygame.Event) -> None:
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.JOYBUTTONDOWN):
            self.elapsed = DURATION

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= DURATION:
            self.manager.replace(TitleScene(self.ctx))

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        canvas.fill(palette.INK)
        fade = min(self.elapsed / FADE, (DURATION - self.elapsed) / FADE, 1.0)
        self.text.set_alpha(round(255 * max(fade, 0.0)))
        canvas.blit(self.text, self.text.get_rect(center=canvas.get_rect().center))
