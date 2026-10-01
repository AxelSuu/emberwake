"""Prefabs: entity templates as data, naming components from a `Registry`.

Example:
    >>> from dataclasses import dataclass
    >>> registry = Registry()
    >>> @registry.register
    ... @dataclass(slots=True)
    ... class Glow:
    ...     radius: float = 8.0
    ...     color: str = "#f9c22b"
    >>> lamp = Prefab(components={"Glow": {"color": "#fbff86"}}, fields={"Radius": "Glow.radius"})
    >>> build(lamp, {"Radius": 20}, registry)
    {'Glow': Glow(radius=20.0, color='#fbff86')}
"""

from __future__ import annotations

import copy
import dataclasses
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs.registry import COMPONENTS, Registry

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


@dataclass(slots=True)
class Prefab:
    """An entity template.

    Attributes:
        components: Component name to field values; missing fields take the class defaults.
        fields: External field (an LDtk field identifier) to ``"Component.field"``.
        persist: Components whose state is saved per entity and restored when it spawns again.
    """

    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)
    persist: list[str] = field(default_factory=list)


def load_prefabs(path: Path) -> dict[str, Prefab]:
    """Read a TOML file of ``[name]`` tables.

    Raises:
        tomllib.TOMLDecodeError: The file is not TOML.
        SerdeError: A table does not describe a prefab.
    """
    return from_data(dict[str, Prefab], tomllib.loads(path.read_text(encoding="utf-8")))


def build(
    prefab: Prefab, values: Mapping[str, Any], registry: Registry = COMPONENTS
) -> dict[str, object]:
    """Instantiate `prefab`'s components with external field `values` mapped in.

    Values that are ``None`` or absent leave the prefab's own value in place.

    Raises:
        KeyError: A component name is not registered.
        SerdeError: A value does not fit its component field.
    """
    data = copy.deepcopy(prefab.components)
    for name, target in prefab.fields.items():
        if values.get(name) is not None:
            component, attribute = target.split(".", 1)
            data.setdefault(component, {})[attribute] = values[name]
    return {name: from_data(registry[name], fields) for name, fields in data.items()}


def check(prefab: Prefab, registry: Registry = COMPONENTS) -> list[str]:
    """Problems with `prefab` that do not depend on field values."""
    problems = [
        f"unknown component {name!r}"
        for name in [*prefab.components, *prefab.persist]
        if name not in registry
    ]
    for external, target in prefab.fields.items():
        component, _, attribute = target.partition(".")
        if component not in registry:
            problems.append(f"{external} maps to unknown component {component!r}")
        elif attribute not in {f.name for f in dataclasses.fields(registry[component])}:
            problems.append(f"{external} maps to missing field {target!r}")
        elif component not in prefab.components:
            problems.append(f"{external} maps to {component}, which the prefab does not have")
    problems.extend(
        f"persists {name}, which the prefab does not have"
        for name in prefab.persist
        if name in registry and name not in prefab.components
    )
    return problems
