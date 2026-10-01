"""Settings overlay: video, audio, accessibility and language, applied as they change."""

from __future__ import annotations

import logging
import tomllib
from typing import TYPE_CHECKING, ClassVar

import pygame

from emberwake.engine.core.serde import SerdeError
from emberwake.engine.platform.documents import save_document
from emberwake.engine.scene import Scene
from emberwake.engine.ui import (
    Button,
    Label,
    Panel,
    ScrollList,
    Selector,
    Slider,
    Theme,
    Toggle,
    UiRoot,
    Widget,
    load_theme,
)
from emberwake.game import paths
from emberwake.game.cosmetics import Cosmetics, load_cosmetics
from emberwake.game.data.settings import SETTINGS_CODEC, SETTINGS_KEY

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

log = logging.getLogger(__name__)

THEME = "ui.toml"
VISIBLE_ROWS = 12
SHADE = 150
SPEEDS = (1.0, 0.75, 0.5)
SPEEDS_LABELS = ["100%", "75%", "50%"]


def load_ui_theme() -> Theme:
    """The shipped widget theme, or the defaults if it cannot be read."""
    try:
        return load_theme(paths.content(THEME))
    except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
        log.error("Could not load %s: %s", THEME, error)
        return Theme()


def _load_cosmetics() -> Cosmetics:
    try:
        return load_cosmetics(paths.content("cosmetics.toml"))
    except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
        log.error("Could not load cosmetics.toml: %s", error)
        return Cosmetics()


class SettingsScene(Scene):
    """Changes `ctx.settings` directly, so everything below picks it up when this closes."""

    blocks_draw: ClassVar[bool] = False

    def __init__(self, ctx: GameContext) -> None:
        self.ctx = ctx
        self.theme = load_ui_theme()
        self.cosmetics = _load_cosmetics()
        self.ui = self._build()

    def on_exit(self) -> None:
        save_document(self.ctx.storage, SETTINGS_KEY, SETTINGS_CODEC, self.ctx.settings)

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
        ctx, video = self.ctx, self.ctx.settings.video
        a11y, audio = self.ctx.settings.accessibility, self.ctx.settings.audio
        assist = self.ctx.settings.assist
        t = ctx.t

        def toggle(key: str, owner: object, field: str) -> Toggle:
            def apply(v: bool) -> None:
                setattr(owner, field, v)

            return Toggle(t(key), getattr(owner, field), apply)

        def slider(key: str, owner: object, field: str) -> Slider:
            def apply(v: float) -> None:
                setattr(owner, field, v)

            return Slider(t(key), getattr(owner, field), on_change=apply)

        cosmetics, cosmetic = self.cosmetics, ctx.settings.cosmetics
        skins, lanterns = list(cosmetics.skins), list(cosmetics.lanterns)
        skin_names = [t(f"skin.{name}") for name in skins]
        lantern_names = [t(f"lantern.{name}") for name in lanterns]
        skin_index = skins.index(cosmetic.skin) if cosmetic.skin in skins else 0
        lantern_index = lanterns.index(cosmetic.lantern) if cosmetic.lantern in lanterns else 0
        speed_index = min(range(len(SPEEDS)), key=lambda i: abs(SPEEDS[i] - assist.game_speed))
        languages = ctx.strings.languages
        chosen = languages.index(ctx.strings.language) if ctx.strings.language in languages else 0
        names = [ctx.strings.tables[code].get("language.name", code) for code in languages]
        rows: list[Widget] = [
            Label(t("settings.video"), dim=True),
            Toggle(t("settings.fullscreen"), video.fullscreen, self._set_fullscreen),
            toggle("settings.vsync", video, "vsync"),
            slider("settings.shake", video, "screen_shake"),
            toggle("settings.bloom", video, "bloom"),
            toggle("settings.grading", video, "grading"),
            toggle("settings.vignette", video, "vignette"),
            toggle("settings.crt", video, "crt"),
            toggle("settings.shadows", video, "shadows"),
            toggle("settings.shafts", video, "light_shafts"),
            Label(t("settings.audio"), dim=True),
            slider("settings.master", audio, "master"),
            slider("settings.music", audio, "music"),
            slider("settings.sfx", audio, "sfx"),
            Button(t("settings.controls"), self._controls),
            Label(t("settings.accessibility"), dim=True),
            toggle("settings.reduce_flashes", a11y, "reduce_flashes"),
            Label(t("settings.cosmetics"), dim=True),
            Selector(t("settings.skin"), skin_names, skin_index, self._set_skin),
            Selector(t("settings.lantern"), lantern_names, lantern_index, self._set_lantern),
            Label(t("settings.assist"), dim=True),
            toggle("settings.invulnerable", assist, "invulnerable"),
            toggle("settings.no_drain", assist, "no_ember_drain"),
            toggle("settings.infinite_dashes", assist, "infinite_dashes"),
            Selector(t("settings.speed"), SPEEDS_LABELS, speed_index, self._set_speed),
            Label(t("settings.language"), dim=True),
            Selector(
                t("settings.language"),
                names,
                chosen,
                lambda i: self._set_language(languages[i]),
            ),
        ]
        list_ = ScrollList(rows, VISIBLE_ROWS)
        back = Button(t("settings.back"), self.close)
        panel = Panel([Label(t("settings.title")), list_, back])
        ui = UiRoot(panel, self.theme, self.close)
        ui.center(ctx.canvas_size)
        inner = panel.children[1]
        assert isinstance(inner, ScrollList)
        if focus is not None:
            inner.index, inner.top = focus, scroll
        return ui

    def close(self) -> None:
        """Leave the screen."""
        self.manager.pop()

    def _controls(self) -> None:
        from emberwake.game.scenes.controls import ControlsScene  # noqa: PLC0415

        self.manager.push(ControlsScene(self.ctx))

    def _set_fullscreen(self, on: bool) -> None:
        self.ctx.settings.video.fullscreen = on
        surface = pygame.display.get_surface()
        if surface is not None and bool(surface.get_flags() & pygame.FULLSCREEN) != on:
            try:
                pygame.display.toggle_fullscreen()
            except pygame.error:
                log.warning("Could not switch fullscreen")

    def _set_skin(self, index: int) -> None:
        self.ctx.settings.cosmetics.skin = list(self.cosmetics.skins)[index]

    def _set_lantern(self, index: int) -> None:
        self.ctx.settings.cosmetics.lantern = list(self.cosmetics.lanterns)[index]

    def _set_speed(self, index: int) -> None:
        self.ctx.settings.assist.game_speed = SPEEDS[index]

    def _set_language(self, code: str) -> None:
        self.ctx.settings.language = code
        self.ctx.strings.language = code
        inner = self.ui.root.children[1]
        assert isinstance(inner, ScrollList)
        self.ui = self._build(inner.index, inner.top)
