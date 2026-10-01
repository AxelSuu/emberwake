"""Front end: continue, new game, load, settings and quit, with a slot picker."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pygame

from emberwake.engine.scene import Scene
from emberwake.engine.ui import Button, Label, Panel, UiRoot
from emberwake.game.data.save import SLOTS, SaveSlot, load_slot
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.settings import SHADE, SettingsScene, load_ui_theme

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.game.context import GameContext


def describe(ctx: GameContext, slot: int, save: SaveSlot | None) -> str:
    """One line for a slot row: its number and where it continues, or that it is empty."""
    if save is None:
        return ctx.t("menu.slot_empty", slot=slot)
    minutes = int(save.playtime // 60)
    room = save.room.replace("_", " ")
    return ctx.t("menu.slot", slot=slot, room=room, h=minutes // 60, m=minutes % 60)


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


def start(ctx: GameContext, scene: Scene, slot: int, *, new: bool) -> None:
    """Play `slot`, from its save or from scratch, replacing the whole front end."""
    ctx.slot, ctx.new_game = slot, new
    scene.manager.switch(GameplayScene(ctx))


class SlotScene(Overlay):
    """Pick a save slot. A new game on an occupied slot asks to be pressed twice."""

    def __init__(self, ctx: GameContext, *, new: bool) -> None:
        self.new = new
        self.armed: int | None = None
        self.saves = {slot: load_slot(ctx.storage, slot) for slot in SLOTS}
        buttons = [
            Button(describe(ctx, slot, self.saves[slot]), lambda slot=slot: self._pick(slot))
            for slot in SLOTS
        ]
        for slot, button in zip(SLOTS, buttons, strict=True):
            button.enabled = new or self.saves[slot] is not None
        self.buttons = dict(zip(SLOTS, buttons, strict=True))
        title = ctx.t("menu.new" if new else "menu.load")
        back = Button(ctx.t("menu.back"), self._back)
        super().__init__(ctx, Panel([Label(title), *buttons, back]), self._back)

    def _label(self, slot: int) -> str:
        return describe(self.ctx, slot, self.saves[slot])

    def _pick(self, slot: int) -> None:
        if self.new and self.saves[slot] is not None and self.armed != slot:
            if self.armed is not None:
                self.buttons[self.armed].text = self._label(self.armed)
            self.armed = slot
            self.buttons[slot].text = self.ctx.t("menu.overwrite", slot=slot)
            self.ui.center(self.ctx.canvas_size)
            return
        start(self.ctx, self, slot, new=self.new)

    def _back(self) -> None:
        self.manager.pop()


class MenuScene(Overlay):
    """Continue, New Game, Load, Settings and Quit over the title screen."""

    def __init__(self, ctx: GameContext) -> None:
        t = ctx.t
        self.last = self._latest(ctx)
        cont = Button(t("menu.continue"), self._continue)
        cont.enabled = self.last is not None
        panel = Panel(
            [
                cont,
                Button(t("menu.new"), lambda: self.manager.push(SlotScene(ctx, new=True))),
                Button(t("menu.load"), lambda: self.manager.push(SlotScene(ctx, new=False))),
                Button(t("menu.settings"), lambda: self.manager.push(SettingsScene(ctx))),
                Button(t("menu.quit"), self._quit),
            ]
        )
        super().__init__(ctx, panel, self._back)

    @staticmethod
    def _latest(ctx: GameContext) -> int | None:
        """The slot to continue: the current one if it has progress, else the most played."""
        saves = {slot: load_slot(ctx.storage, slot) for slot in SLOTS}
        if saves.get(ctx.slot) is not None:
            return ctx.slot
        played = [(save.playtime, slot) for slot, save in saves.items() if save is not None]
        return max(played)[1] if played else None

    def _continue(self) -> None:
        if self.last is not None:
            start(self.ctx, self, self.last, new=False)

    def _back(self) -> None:
        self.manager.pop()

    def _quit(self) -> None:
        self.manager.close()
