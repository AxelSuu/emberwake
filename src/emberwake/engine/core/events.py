"""Typed publish/subscribe event bus.

Events are plain objects (usually frozen dataclasses). Handlers subscribe to an exact event
type, so publishing a subclass does not reach handlers of its base class.

Example:
    >>> from dataclasses import dataclass
    >>> @dataclass(frozen=True)
    ... class Scored:
    ...     points: int
    >>> bus = EventBus()
    >>> total = []
    >>> unsubscribe = bus.subscribe(Scored, lambda e: total.append(e.points))
    >>> bus.publish(Scored(10))
    >>> total
    [10]
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

type Handler[E] = Callable[[E], None]


class EventBus:
    """Dispatches events to handlers, either immediately or queued until `flush`."""

    def __init__(self) -> None:
        self._handlers: defaultdict[type, list[Handler[Any]]] = defaultdict(list)
        self._queue: list[object] = []

    def subscribe[E](self, event_type: type[E], handler: Handler[E]) -> Callable[[], None]:
        """Register `handler` for `event_type` and return a function that unsubscribes it."""
        handlers = self._handlers[event_type]
        handlers.append(handler)

        def unsubscribe() -> None:
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def publish(self, event: object) -> None:
        """Deliver `event` to its handlers now."""
        # Copy so handlers may unsubscribe themselves while being called.
        for handler in tuple(self._handlers.get(type(event), ())):
            handler(event)

    def emit(self, event: object) -> None:
        """Queue `event` for delivery on the next `flush`."""
        self._queue.append(event)

    def flush(self) -> None:
        """Deliver queued events in order, including ones emitted while flushing."""
        while self._queue:
            queue, self._queue = self._queue, []
            for event in queue:
                self.publish(event)
