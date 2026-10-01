"""Menu navigation: keyboard and gamepad events become `Nav` actions, with hold-to-repeat."""

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
BUTTONS = {
    pygame.CONTROLLER_BUTTON_DPAD_UP: Nav.UP,
    pygame.CONTROLLER_BUTTON_DPAD_DOWN: Nav.DOWN,
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: Nav.LEFT,
    pygame.CONTROLLER_BUTTON_DPAD_RIGHT: Nav.RIGHT,
    pygame.CONTROLLER_BUTTON_A: Nav.ACCEPT,
    pygame.CONTROLLER_BUTTON_B: Nav.BACK,
}
STICK_ON = 0.6
STICK_OFF = 0.3
REPEATING = frozenset({Nav.UP, Nav.DOWN, Nav.LEFT, Nav.RIGHT})
DELAY = 0.35
INTERVAL = 0.08


class Navigator:
    """Turns events into `Nav` presses and repeats a held direction after a short delay."""

    def __init__(self) -> None:
        self._held: Nav | None = None
        self._timer = 0.0
        self._stick: dict[int, Nav | None] = {}

    def handle(self, event: pygame.Event) -> Nav | None:
        """The action a press event stands for, or None; releases stop any repeat."""
        if event.type == pygame.KEYDOWN:
            return self._press(KEYS.get(event.key))
        if event.type == pygame.CONTROLLERBUTTONDOWN:
            return self._press(BUTTONS.get(event.button))
        if event.type == pygame.KEYUP:
            self._release(KEYS.get(event.key))
        elif event.type == pygame.CONTROLLERBUTTONUP:
            self._release(BUTTONS.get(event.button))
        elif event.type == pygame.CONTROLLERAXISMOTION:
            return self._axis(event.axis, event.value)
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

    def _axis(self, axis: int, value: float) -> Nav | None:
        if axis not in (pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY):
            return None
        horizontal = axis == pygame.CONTROLLER_AXIS_LEFTX
        negative, positive = (Nav.LEFT, Nav.RIGHT) if horizontal else (Nav.UP, Nav.DOWN)
        current = self._stick.get(axis)
        if abs(value) < STICK_OFF:
            if current is not None and current == self._held:
                self._held = None
            self._stick[axis] = None
            return None
        if abs(value) < STICK_ON or current is not None:
            return None
        self._stick[axis] = positive if value > 0 else negative
        return self._press(self._stick[axis])
