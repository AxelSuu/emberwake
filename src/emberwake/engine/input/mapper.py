"""Map keyboard and gamepad events to game actions.

Held keys and buttons are tracked from events rather than polled, so the mapper behaves the
same in tests, replays and the browser, and a press and release inside one frame (a tap) still
reaches the game as one tick of the action being held.

Gamepads use SDL's game controller API, which normalizes button layout across devices. Stick
directions act as virtual buttons named ``leftx-``, ``leftx+``, ``lefty-``, ``lefty+`` (and the
same for ``rightx``/``righty``, plus ``lefttrigger+``/``righttrigger+``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import pygame

if TYPE_CHECKING:
    from collections.abc import Iterable

try:
    from pygame._sdl2 import controller as sdl_controller
except ImportError:  # pragma: no cover - platforms without the SDL2 controller module
    sdl_controller = None

log = logging.getLogger(__name__)

STICK_THRESHOLD = 0.5
AXIS_MAX = 32767

BUTTONS: dict[str, int] = {
    "a": pygame.CONTROLLER_BUTTON_A,
    "b": pygame.CONTROLLER_BUTTON_B,
    "x": pygame.CONTROLLER_BUTTON_X,
    "y": pygame.CONTROLLER_BUTTON_Y,
    "back": pygame.CONTROLLER_BUTTON_BACK,
    "start": pygame.CONTROLLER_BUTTON_START,
    "leftstick": pygame.CONTROLLER_BUTTON_LEFTSTICK,
    "rightstick": pygame.CONTROLLER_BUTTON_RIGHTSTICK,
    "leftshoulder": pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    "rightshoulder": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    "dpad_up": pygame.CONTROLLER_BUTTON_DPAD_UP,
    "dpad_down": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
    "dpad_left": pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    "dpad_right": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
}
AXES: dict[int, str] = {
    pygame.CONTROLLER_AXIS_LEFTX: "leftx",
    pygame.CONTROLLER_AXIS_LEFTY: "lefty",
    pygame.CONTROLLER_AXIS_RIGHTX: "rightx",
    pygame.CONTROLLER_AXIS_RIGHTY: "righty",
    pygame.CONTROLLER_AXIS_TRIGGERLEFT: "lefttrigger",
    pygame.CONTROLLER_AXIS_TRIGGERRIGHT: "righttrigger",
}
_BUTTON_NAMES = {code: name for name, code in BUTTONS.items()}
_VIRTUAL_BUTTONS = {f"{axis}{sign}" for axis in AXES.values() for sign in "-+"}


@dataclass(slots=True)
class Bindings:
    """Action names mapped to key names (`pygame.key.key_code`) and gamepad button names.

    Plain strings keep ``settings.json`` readable and editable by hand.
    """

    keys: dict[str, list[str]] = field(default_factory=dict)
    buttons: dict[str, list[str]] = field(default_factory=dict)


class InputMapper[A: Enum]:
    """Turns device events into one frame of held actions per `sample`.

    Args:
        actions: The game's action enum; binding names are its values.
        bindings: Initial bindings.
    """

    def __init__(self, actions: type[A], bindings: Bindings) -> None:
        self._actions = actions
        self._key_map: dict[int, set[A]] = {}
        self._button_map: dict[str, set[A]] = {}
        self._held_keys: set[int] = set()
        self._held_buttons: set[str] = set()
        self._tapped: set[A] = set()
        self._controllers: list[Any] = []
        self.bind(bindings)
        if sdl_controller is not None and not sdl_controller.get_init():
            sdl_controller.init()

    def bind(self, bindings: Bindings) -> None:
        """Replace all bindings. Unknown actions, keys or buttons are logged and skipped."""
        self._key_map = {}
        for action, key in self._resolve(bindings.keys):
            try:
                code = pygame.key.key_code(key)
            except ValueError:
                log.warning("Unknown key %r bound to %s", key, action)
                continue
            self._key_map.setdefault(code, set()).add(action)
        self._button_map = {}
        for action, button in self._resolve(bindings.buttons):
            if button not in BUTTONS and button not in _VIRTUAL_BUTTONS:
                log.warning("Unknown gamepad button %r bound to %s", button, action)
                continue
            self._button_map.setdefault(button, set()).add(action)

    def handle(self, event: pygame.Event) -> None:
        """Track device state from `event`. Unrelated events are ignored."""
        match event.type:
            case pygame.KEYDOWN:
                self._held_keys.add(event.key)
                self._tapped |= self._key_map.get(event.key, set())
            case pygame.KEYUP:
                self._held_keys.discard(event.key)
            case pygame.CONTROLLERBUTTONDOWN if event.button in _BUTTON_NAMES:
                self._press_button(_BUTTON_NAMES[event.button])
            case pygame.CONTROLLERBUTTONUP if event.button in _BUTTON_NAMES:
                self._held_buttons.discard(_BUTTON_NAMES[event.button])
            case pygame.CONTROLLERAXISMOTION if event.axis in AXES:
                self._move_axis(AXES[event.axis], event.value / AXIS_MAX)
            case pygame.CONTROLLERDEVICEADDED:
                self._open_controller(event.device_index)
            case pygame.CONTROLLERDEVICEREMOVED:
                self._controllers = [c for c in self._controllers if c.attached()]
                self._held_buttons.clear()
            case pygame.WINDOWFOCUSLOST:
                self._held_keys.clear()
                self._held_buttons.clear()

    def sample(self) -> frozenset[A]:
        """Return the actions held since the last sample, including taps already released."""
        held = set(self._tapped)
        for key in self._held_keys:
            held |= self._key_map.get(key, set())
        for button in self._held_buttons:
            held |= self._button_map.get(button, set())
        self._tapped.clear()
        return frozenset(held)

    def _resolve(self, table: dict[str, list[str]]) -> Iterable[tuple[A, str]]:
        for name, inputs in table.items():
            try:
                action = self._actions(name)
            except ValueError:
                log.warning("Bindings name unknown action %r", name)
                continue
            for item in inputs:
                yield action, item

    def _press_button(self, name: str) -> None:
        if name not in self._held_buttons:
            self._held_buttons.add(name)
            self._tapped |= self._button_map.get(name, set())

    def _move_axis(self, axis: str, value: float) -> None:
        for sign, active in (("-", value < -STICK_THRESHOLD), ("+", value > STICK_THRESHOLD)):
            if active:
                self._press_button(axis + sign)
            else:
                self._held_buttons.discard(axis + sign)

    def _open_controller(self, device_index: int) -> None:
        if sdl_controller is None:
            return
        try:
            pad = sdl_controller.Controller(device_index)
        except pygame.error:
            log.exception("Could not open controller %d", device_index)
            return
        log.info("Controller connected: %s", pad.name)
        self._controllers.append(pad)
