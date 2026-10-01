from dataclasses import dataclass

from emberwake.engine.core.events import EventBus


@dataclass(frozen=True)
class Ping:
    n: int


@dataclass(frozen=True)
class SubPing(Ping):
    pass


def test_publish_reaches_exact_type_only():
    bus = EventBus()
    got: list[int] = []
    bus.subscribe(Ping, lambda e: got.append(e.n))
    bus.publish(Ping(1))
    bus.publish(SubPing(2))
    assert got == [1]


def test_unsubscribe():
    bus = EventBus()
    got: list[int] = []
    unsubscribe = bus.subscribe(Ping, lambda e: got.append(e.n))
    unsubscribe()
    unsubscribe()
    bus.publish(Ping(1))
    assert got == []


def test_handler_may_unsubscribe_itself_during_publish():
    bus = EventBus()
    got: list[str] = []

    def once(_: Ping) -> None:
        got.append("once")
        unsubscribe()

    unsubscribe = bus.subscribe(Ping, once)
    bus.subscribe(Ping, lambda _: got.append("always"))
    bus.publish(Ping(0))
    bus.publish(Ping(0))
    assert got == ["once", "always", "always"]


def test_emit_defers_until_flush_including_nested_emits():
    bus = EventBus()
    got: list[int] = []

    def chain(e: Ping) -> None:
        got.append(e.n)
        if e.n < 3:
            bus.emit(Ping(e.n + 1))

    bus.subscribe(Ping, chain)
    bus.emit(Ping(1))
    assert got == []
    bus.flush()
    assert got == [1, 2, 3]
