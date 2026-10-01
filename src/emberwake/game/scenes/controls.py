"""Controls overlay: rebind keyboard and gamepad actions, with conflict handling and reset."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pygame

from emberwake.engine.platform.documents import save_document
from emberwake.engine.scene import Scene
from emberwake.engine.ui import Button, KeybindField, Label, Panel, ScrollList, UiRoot, Widget
from emberwake.game.actions import Action
from emberwake.game.data.settings import SETTINGS_CODEC, SETTINGS_KEY
from emberwake.game.rebind import primary, rebind, reset
from emberwake.game.scenes.settings import SHADE, VISIBLE_ROWS, load_ui_theme

if TYPE_CHECKING:
    from emberwake.game.context import GameContext


LABELS = {
    Action.LEFT: "action.left",
    Action.RIGHT: "action.right",
    Action.UP: "action.up",
    Action.DOWN: "action.down",
    Action.JUMP: "action.jump",
    Action.DASH: "action.dash",
    Action.INTERACT: "action.interact",
}


class ControlsScene(Scene):
    """Edits ``ctx.settings.controls`` in place; settings are saved when the overlay closes."""

    blocks_draw: ClassVar[bool] = False

    def __init__(self, ctx: GameContext) -> None:
        self.ctx = ctx
        self.theme = load_ui_theme()
        self.notice = Label("", dim=True)
        self.ui = self._build()

    def handle(self, event: pygame.Event) -> None:
        self.ui.handle(event)

    def update(self, dt: float) -> None:
        self.ui.update(dt)

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        shade = pygame.Surface(canvas.get_size())
        shade.set_alpha(SHADE)
        canvas.blit(shade, (0, 0))
        self.ui.draw(canvas)

    def _build(self, focus: int | None = None, scroll: float = 0.0) -> UiRoot:
        ctx = self.ctx
        controls = ctx.settings.controls
        rows: list[Widget] = []
        tables = (("controls.keyboard", controls.keys), ("controls.gamepad", controls.buttons))
        for heading, table in tables:
            rows.append(Label(ctx.t(heading), dim=True))
            rows.extend(
                KeybindField(
                    ctx.t(LABELS[action]),
                    primary(table, action),
                    lambda name, table=table, action=action: self._bind(table, action, name),
                )
                for action in Action
            )
        rows.append(Button(ctx.t("controls.reset"), self._reset))
        list_ = ScrollList(rows, VISIBLE_ROWS)
        back = Button(ctx.t("controls.back"), self.close)
        panel = Panel([Label(ctx.t("controls.title")), list_, self.notice, back])
        ui = UiRoot(panel, self.theme, self.close)
        ui.center(ctx.canvas_size)
        if focus is not None:
            list_.index, list_.top = focus, scroll
        return ui

    def _rebuild(self) -> None:
        inner = self.ui.root.children[1]
        assert isinstance(inner, ScrollList)
        self.ui = self._build(inner.index, inner.top)

    def _bind(self, table: dict[str, list[str]], action: Action, name: str) -> None:
        taken = rebind(table, action, name)
        self.notice.text = ""
        if taken:
            other = self.ctx.t(LABELS[taken])
            self.notice.text = self.ctx.t("controls.moved", input=name, action=other)
        self._rebuild()

    def _reset(self) -> None:
        reset(self.ctx.settings.controls)
        self.notice.text = ""
        self._rebuild()

    def on_exit(self) -> None:
        save_document(self.ctx.storage, SETTINGS_KEY, SETTINGS_CODEC, self.ctx.settings)

    def close(self) -> None:
        self.manager.pop()
