"""The map screen: the current area's rooms, beacons, people, the Cinder and you."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.scene import Scene
from emberwake.engine.ui import Button, Panel, UiRoot
from emberwake.game import palette
from emberwake.game.map import Icon
from emberwake.game.scenes.settings import load_ui_theme

if TYPE_CHECKING:
    from emberwake.game.context import GameContext
    from emberwake.game.map import MapView

MARGIN = 24
TITLE_GAP = 28
BLINK = 0.5

ICONS = {
    Icon.BEACON_LIT: (palette.EMBER_CORE, 2),
    Icon.BEACON_COLD: (palette.HORIZON, 2),
    Icon.NPC: (palette.MIST, 1),
    Icon.CINDER: (palette.EMBER_WARM, 2),
    Icon.PLAYER: (palette.EMBER_HOT, 2),
}
"""Color and half-size in px of each icon's square."""


def map_box(canvas_size: tuple[int, int]) -> pygame.Rect:
    """Where the area is drawn: the canvas minus the margins, the title and the Back button."""
    width, height = canvas_size
    top = MARGIN + TITLE_GAP
    return pygame.Rect(MARGIN, top, width - 2 * MARGIN, height - 2 * top)


class MapScene(Scene):
    """Draws a `MapView` over a dark screen; Back or M closes it."""

    def __init__(self, ctx: GameContext, view: MapView, title: tuple[str, str]) -> None:
        self.ctx, self.view, self.title = ctx, view, title
        self.clock = 0.0
        back = Panel([Button(ctx.t("map.back"), self._back)])
        self.ui = UiRoot(back, load_ui_theme(), self._back)
        width, height = self.ui.root.preferred(self.ui.theme)
        rect = pygame.Rect(0, 0, width, height)
        rect.midbottom = (ctx.canvas_size[0] // 2, ctx.canvas_size[1] - MARGIN // 4)
        self.ui.layout(rect)

    def handle(self, event: pygame.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            self._back()
            return
        self.ui.handle(event)

    def update(self, dt: float) -> None:
        self.clock += dt
        self.ui.update(dt)

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        canvas.fill(palette.INK)
        theme = self.ui.theme
        y = MARGIN // 2
        for line, color in zip(self.title, ("text", "dim"), strict=True):
            if line:
                text = theme.render(line, color)
                canvas.blit(text, ((canvas.get_width() - text.get_width()) // 2, y))
                y += text.get_height() + 2
        for room in self.view.rooms:
            if room.visited:
                pygame.draw.rect(canvas, palette.NIGHT, room.rect)
            pygame.draw.rect(canvas, palette.DUSK, room.rect, 1)
        shown = (self.clock % (2 * BLINK)) < BLINK
        for icon in self.view.icons:
            if icon.kind is Icon.PLAYER and not shown:
                continue
            color, half = ICONS[icon.kind]
            square = pygame.Rect(icon.x - half, icon.y - half, 2 * half + 1, 2 * half + 1)
            pygame.draw.rect(canvas, color, square)
        self.ui.draw(canvas)

    def _back(self) -> None:
        self.manager.pop()
