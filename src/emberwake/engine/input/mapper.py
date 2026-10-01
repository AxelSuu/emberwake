"""Map keyboard events to game actions.

Held keys are tracked from events rather than polled, so the mapper behaves the
same in tests, replays and the browser, and a press and release inside one frame (a tap) still
reaches the game as one tick of the action being held.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from collections.abc import Iterable

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Bindings:
    """Action names mapped to key names (`pygame.key.key_code`).

    Plain strings keep ``settings.json`` readable and editable by hand.
    """

    keys: dict[str, list[str]] = field(default_factory=dict)


class InputMapper[A: Enum]:
    """Turns device events into one frame of held actions per `sample`.

    Args:
        actions: The game's action enum; binding names are its values.
        bindings: Initial bindings.
    """

    def __init__(self, actions: type[A], bindings: Bindings) -> None:
        self._actions = actions
        self._key_map: dict[int, set[A]] = {}
        self._held_keys: set[int] = set()
        self._tapped: set[A] = set()
        self.bind(bindings)

    def bind(self, bindings: Bindings) -> None:
        """Replace all bindings. Unknown actions or keys are logged and skipped."""
        self._key_map = {}
        for action, key in self._resolve(bindings.keys):
            try:
                code = pygame.key.key_code(key)
            except ValueError:
                log.warning("Unknown key %r bound to %s", key, action)
                continue
            self._key_map.setdefault(code, set()).add(action)

    def handle(self, event: pygame.Event) -> None:
        """Track device state from `event`. Unrelated events are ignored."""
        match event.type:
            case pygame.KEYDOWN:
                self._held_keys.add(event.key)
                self._tapped |= self._key_map.get(event.key, set())
            case pygame.KEYUP:
                self._held_keys.discard(event.key)
            case pygame.WINDOWFOCUSLOST:
                self._held_keys.clear()

    def release_all(self) -> None:
        """Forget every held key, such as when another screen took the input."""
        self._held_keys.clear()
        self._tapped.clear()

    def sample(self) -> frozenset[A]:
        """Return the actions held since the last sample, including taps already released."""
        held = set(self._tapped)
        for key in self._held_keys:
            held |= self._key_map.get(key, set())
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
