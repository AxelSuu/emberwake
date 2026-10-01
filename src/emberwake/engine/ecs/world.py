"""Entities, component stores, typed queries and resources.

Structural changes (`World.spawn`, `World.add`, `World.remove`, `World.despawn`) are queued and
applied in order by `World.flush`, so systems never change a store they are iterating.
`Schedule.run` flushes between phases; code outside a schedule calls `flush` itself.

Example:
    >>> from dataclasses import dataclass
    >>> @dataclass(slots=True)
    ... class Pos:
    ...     x: float
    >>> @dataclass(slots=True)
    ... class Vel:
    ...     dx: float
    >>> world = World()
    >>> mover = world.spawn(Pos(0.0), Vel(2.0))
    >>> rock = world.spawn(Pos(5.0))
    >>> world.flush()
    >>> for _, pos, vel in world.query(Pos, Vel):
    ...     pos.x += vel.dx
    >>> world.get(mover, Pos), world.get(rock, Pos)
    (Pos(x=2.0), Pos(x=5.0))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NewType, overload

if TYPE_CHECKING:
    from collections.abc import Iterator

EntityId = NewType("EntityId", int)


class World:
    """Holds entities as component stores keyed by component type, plus resources."""

    def __init__(self) -> None:
        self._next_id = 0
        self._alive: set[EntityId] = set()
        self._stores: dict[type, dict[EntityId, Any]] = {}
        self._resources: dict[type, Any] = {}
        self._pending: list[tuple[str, EntityId, tuple[Any, ...]]] = []

    # Structural changes, deferred until `flush`

    def spawn(self, *components: object) -> EntityId:
        """Reserve a new entity now; it and its `components` appear on the next `flush`."""
        eid = EntityId(self._next_id)
        self._next_id += 1
        self._pending.append(("spawn", eid, components))
        return eid

    def add(self, eid: EntityId, *components: object) -> None:
        """Attach `components` on the next `flush`, replacing any of the same type."""
        self._pending.append(("add", eid, components))

    def remove(self, eid: EntityId, *types: type) -> None:
        """Detach the components of `types` on the next `flush`; missing ones are ignored."""
        self._pending.append(("remove", eid, types))

    def despawn(self, eid: EntityId) -> None:
        """Delete the entity and all its components on the next `flush`."""
        self._pending.append(("despawn", eid, ()))

    def flush(self) -> None:
        """Apply queued structural changes in the order they were made.

        Changes to entities that are already despawned are dropped. Never call this while
        iterating a query.
        """
        pending, self._pending = self._pending, []
        for op, eid, args in pending:
            if op == "spawn":
                self._alive.add(eid)
            elif eid not in self._alive:
                continue
            if op in ("spawn", "add"):
                for component in args:
                    self._stores.setdefault(type(component), {})[eid] = component
            elif op == "remove":
                for tp in args:
                    self._stores.get(tp, {}).pop(eid, None)
            else:
                self._alive.discard(eid)
                for store in self._stores.values():
                    store.pop(eid, None)

    # Access

    def __contains__(self, eid: object) -> bool:
        return eid in self._alive

    def __len__(self) -> int:
        return len(self._alive)

    def reserved(self, eid: EntityId) -> bool:
        """Whether `eid` is alive or spawned and waiting for the next `flush`."""
        return eid in self._alive or any(
            op == "spawn" and pending == eid for op, pending, _ in self._pending
        )

    def get[C](self, eid: EntityId, tp: type[C]) -> C:
        """The `tp` component of `eid`.

        Raises:
            KeyError: The entity is not alive or has no such component.
        """
        return self._stores[tp][eid]

    def find[C](self, eid: EntityId, tp: type[C]) -> C | None:
        """The `tp` component of `eid`, or ``None``."""
        store = self._stores.get(tp)
        return None if store is None else store.get(eid)

    def has(self, eid: EntityId, *types: type) -> bool:
        """Whether `eid` has a component of every one of `types`."""
        return all(eid in self._stores.get(tp, ()) for tp in types)

    def count(self, tp: type) -> int:
        """How many entities have a `tp` component."""
        return len(self._stores.get(tp, ()))

    @overload
    def query[A](self, a: type[A], /) -> Iterator[tuple[EntityId, A]]: ...
    @overload
    def query[A, B](self, a: type[A], b: type[B], /) -> Iterator[tuple[EntityId, A, B]]: ...
    @overload
    def query[A, B, C](
        self, a: type[A], b: type[B], c: type[C], /
    ) -> Iterator[tuple[EntityId, A, B, C]]: ...
    @overload
    def query[A, B, C, D](
        self, a: type[A], b: type[B], c: type[C], d: type[D], /
    ) -> Iterator[tuple[EntityId, A, B, C, D]]: ...
    def query(self, *types: type) -> Iterator[tuple[Any, ...]]:
        """Yield ``(eid, *components)`` for every entity that has all of `types`.

        Iterates the smallest of the stores, in the order entities got that component.
        """
        stores: list[dict[EntityId, Any]] = []
        for tp in types:
            store = self._stores.get(tp)
            if not store:
                return iter(())
            stores.append(store)
        if len(stores) == 1:
            return iter(stores[0].items())
        if len(stores) == 2:
            return _pairs(*stores)
        return _rows(stores)

    # Resources

    def insert_resource(self, value: object, key: type | None = None) -> None:
        """Store a world singleton under `key` (default: its own type), replacing any old one."""
        self._resources[type(value) if key is None else key] = value

    def resource[R](self, key: type[R]) -> R:
        """The resource stored under `key`.

        Raises:
            KeyError: No such resource.
        """
        return self._resources[key]

    def has_resource(self, key: type) -> bool:
        """Whether a resource is stored under `key`."""
        return key in self._resources


def _pairs(a: dict[EntityId, Any], b: dict[EntityId, Any]) -> Iterator[tuple[Any, ...]]:
    if len(a) <= len(b):
        for eid, first in a.items():
            if eid in b:
                yield eid, first, b[eid]
    else:
        for eid, second in b.items():
            if eid in a:
                yield eid, a[eid], second


def _rows(stores: list[dict[EntityId, Any]]) -> Iterator[tuple[Any, ...]]:
    smallest = min(stores, key=len)
    others = [store for store in stores if store is not smallest]
    for eid in smallest:
        for store in others:
            if eid not in store:
                break
        else:
            yield (eid, *[store[eid] for store in stores])
