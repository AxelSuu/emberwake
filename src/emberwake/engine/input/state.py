"""Per-tick action state with edge detection and press buffering."""

from __future__ import annotations

from collections.abc import Hashable


class InputState[A: Hashable]:
    """The set of actions held this tick, compared against the previous tick.

    Feed it exactly one frame (the set of held actions) per simulation tick with `advance`.
    Everything else is derived, so the same frames always produce the same queries; this is
    what makes replays exact.

    Example:
        >>> state = InputState[str]()
        >>> state.advance(frozenset({"jump"}))
        >>> state.pressed("jump"), state.down("jump")
        (True, True)
        >>> state.advance(frozenset())
        >>> state.released("jump"), state.pressed_within("jump", 2)
        (True, True)
    """

    def __init__(self) -> None:
        self.tick = 0
        self._down: frozenset[A] = frozenset()
        self._previous: frozenset[A] = frozenset()
        self._pressed_at: dict[A, int] = {}

    @property
    def frame(self) -> frozenset[A]:
        """Actions held this tick."""
        return self._down

    def advance(self, frame: frozenset[A]) -> None:
        """Start a new tick with the actions in `frame` held."""
        self.tick += 1
        self._previous, self._down = self._down, frame
        for action in frame - self._previous:
            self._pressed_at[action] = self.tick

    def down(self, action: A) -> bool:
        """Whether `action` is held this tick."""
        return action in self._down

    def pressed(self, action: A) -> bool:
        """Whether `action` went down this tick."""
        return action in self._down and action not in self._previous

    def released(self, action: A) -> bool:
        """Whether `action` went up this tick."""
        return action in self._previous and action not in self._down

    def pressed_within(self, action: A, ticks: int) -> bool:
        """Whether `action` went down during the last `ticks` ticks (this one included)."""
        pressed_at = self._pressed_at.get(action)
        return pressed_at is not None and self.tick - pressed_at < ticks

    def consume(self, action: A) -> None:
        """Forget the buffered press of `action` so it cannot trigger twice."""
        self._pressed_at.pop(action, None)

    def axis(self, negative: A, positive: A) -> int:
        """``-1``, ``0`` or ``1`` from a pair of opposing actions."""
        return (positive in self._down) - (negative in self._down)
