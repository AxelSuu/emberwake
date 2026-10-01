"""Menu navigation: keyboard events become `Nav` actions, with hold-to-repeat."""

from __future__ import annotations

from enum import StrEnum

import pygame


class Nav(StrEnum):
    """What a menu input means."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ACCEPT = "accept"
    BACK = "back"


KEYS = {
    pygame.K_UP: Nav.UP,
    pygame.K_w: Nav.UP,
    pygame.K_DOWN: Nav.DOWN,
    pygame.K_s: Nav.DOWN,
    pygame.K_LEFT: Nav.LEFT,
    pygame.K_a: Nav.LEFT,
    pygame.K_RIGHT: Nav.RIGHT,
    pygame.K_d: Nav.RIGHT,
    pygame.K_RETURN: Nav.ACCEPT,
    pygame.K_SPACE: Nav.ACCEPT,
    pygame.K_ESCAPE: Nav.BACK,
    pygame.K_BACKSPACE: Nav.BACK,
}
REPEATING = frozenset({Nav.UP, Nav.DOWN, Nav.LEFT, Nav.RIGHT})
DELAY = 0.35
INTERVAL = 0.08


class Navigator:
    """Turns events into `Nav` presses and repeats a held direction after a short delay."""

    def __init__(self) -> None:
        self._held: Nav | None = None
        self._timer = 0.0

    def handle(self, event: pygame.Event) -> Nav | None:
        """The action a press event stands for, or None; releases stop any repeat."""
        if event.type == pygame.KEYDOWN:
            return self._press(KEYS.get(event.key))
        if event.type == pygame.KEYUP:
            self._release(KEYS.get(event.key))
        return None

    def update(self, dt: float) -> Nav | None:
        """A repeated press of the held direction, once its delay or interval has passed."""
        if self._held is None:
            return None
        self._timer -= dt
        if self._timer > 0:
            return None
        self._timer = INTERVAL
        return self._held

    def _release(self, nav: Nav | None) -> None:
        if nav is not None and nav == self._held:
            self._held = None

    def _press(self, nav: Nav | None) -> Nav | None:
        if nav in REPEATING:
            self._held, self._timer = nav, DELAY
        return nav
