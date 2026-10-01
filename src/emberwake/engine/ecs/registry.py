"""Component classes by name, so prefabs and saves can refer to them as text."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


class Registry:
    """Maps component names to dataclass types.

    Example:
        >>> from dataclasses import dataclass
        >>> registry = Registry()
        >>> @registry.register
        ... @dataclass(slots=True)
        ... class Health:
        ...     hp: int = 3
        >>> registry["Health"]()
        Health(hp=3)
    """

    def __init__(self) -> None:
        self._types: dict[str, type[Any]] = {}

    def register[T: type](self, cls: T) -> T:
        """Register `cls` under its class name; usable as a decorator.

        Raises:
            TypeError: `cls` is not a dataclass, so serde could not save it.
            ValueError: Another class is already registered under the same name.
        """
        if not dataclasses.is_dataclass(cls):
            msg = f"{cls.__name__} must be a dataclass to be a component"
            raise TypeError(msg)
        known = self._types.setdefault(cls.__name__, cls)
        if known is not cls:
            msg = f"component name {cls.__name__!r} is taken by {known.__module__}"
            raise ValueError(msg)
        return cls

    def __getitem__(self, name: str) -> type[Any]:
        try:
            return self._types[name]
        except KeyError:
            msg = f"unknown component {name!r}"
            raise KeyError(msg) from None

    def __contains__(self, name: object) -> bool:
        return name in self._types

    def __iter__(self) -> Iterator[str]:
        return iter(self._types)


COMPONENTS = Registry()
"""The registry `component` adds to."""


def component[T: type](cls: T) -> T:
    """Class decorator registering a component dataclass in `COMPONENTS`."""
    return COMPONENTS.register(cls)
