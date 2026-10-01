"""The top of a UI tree: lays it out, feeds it events and draws it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.ui.nav import Nav, Navigator

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.ui.theme import Theme
    from emberwake.engine.ui.widgets import Container


class UiRoot:
    """One screen of widgets. Back (escape, gamepad B) calls `on_back`."""

    def __init__(
        self, root: Container, theme: Theme, on_back: Callable[[], None] | None = None
    ) -> None:
        self.root, self.theme, self.on_back = root, theme, on_back
        self.navigator = Navigator()
        self.root.focused = True

    def layout(self, rect: pygame.Rect) -> None:
        """Place the tree inside `rect`."""
        self.root.layout(rect, self.theme)

    def center(self, canvas_size: tuple[int, int]) -> None:
        """Lay out at the root's preferred size, centred on a canvas."""
        width, height = self.root.preferred(self.theme)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (canvas_size[0] // 2, canvas_size[1] // 2)
        self.layout(rect)

    def handle(self, event: pygame.Event) -> None:
        """Route an event: a capturing widget gets it raw, otherwise it navigates."""
        if self.root.capturing:
            self.root.capture(event)
            return
        nav = self.navigator.handle(event)
        if nav is not None:
            self.press(nav)

    def press(self, nav: Nav) -> None:
        """Apply one navigation action."""
        if nav is Nav.BACK:
            if self.on_back:
                self.on_back()
        else:
            self.root.navigate(nav)

    def update(self, dt: float) -> None:
        """Repeat a held direction and ease the focus highlights."""
        repeat = None if self.root.capturing else self.navigator.update(dt)
        if repeat is not None:
            self.press(repeat)
        self.root.update(dt, self.theme)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the tree."""
        self.root.draw(surface, self.theme)
