"""Check that every LDtk entity spawns: it has a prefab, and its fields fit the prefab."""

from __future__ import annotations

from typing import TYPE_CHECKING

import emberwake.game.components  # noqa: F401  (registers the components prefabs name)
from emberwake.engine.core.serde import SerdeError
from emberwake.engine.ecs import COMPONENTS
from emberwake.engine.ecs.prefabs import build, check
from emberwake.engine.world.spawning import prefab_name

if TYPE_CHECKING:
    from collections.abc import Mapping

    from emberwake.engine.ecs import Registry
    from emberwake.engine.ecs.prefabs import Prefab
    from emberwake.engine.world.ldtk import Project


def validate(
    project: Project, prefabs: Mapping[str, Prefab], registry: Registry = COMPONENTS
) -> list[str]:
    """Problems found, one line each; empty when every entity would spawn."""
    problems = [
        f"prefab {name}: {problem}"
        for name, prefab in prefabs.items()
        for problem in check(prefab, registry)
    ]
    missing: set[str] = set()
    for level in project.all_levels:
        for entity in level.entities():
            name = prefab_name(entity.identifier)
            prefab = prefabs.get(name)
            if prefab is None:
                if name not in missing:
                    missing.add(name)
                    problems.append(f"{entity.identifier}: no prefab [{name}]")
                continue
            where = f"{level.identifier} {entity.identifier} {entity.iid}"
            values = entity.values()
            unknown = sorted(prefab.fields.keys() - values.keys())
            if unknown:
                problems.append(f"{where}: no LDtk fields {unknown} for prefab {name}")
            try:
                build(prefab, values, registry)
            except (KeyError, SerdeError) as error:
                problems.append(f"{where}: {error}")
    return problems
