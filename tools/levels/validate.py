"""Check that every LDtk entity spawns (it has a prefab its fields fit) and level fields fit."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import emberwake.game.components  # noqa: F401  (registers every game component)
from emberwake.engine.core.serde import SerdeError
from emberwake.engine.ecs import COMPONENTS
from emberwake.engine.ecs.prefabs import build, check
from emberwake.engine.world.spawning import prefab_name
from emberwake.game.areas import NAME

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from emberwake.engine.ecs import Registry
    from emberwake.engine.ecs.prefabs import Prefab
    from emberwake.engine.world.ldtk import Level, Project
    from emberwake.game.areas import Areas


def validate(
    project: Project,
    prefabs: Mapping[str, Prefab],
    registry: Registry = COMPONENTS,
    backdrops: Collection[str] | None = None,
    areas: Areas | None = None,
) -> list[str]:
    """Problems found, one line each; empty when every entity would spawn."""
    problems = [
        f"prefab {name}: {problem}"
        for name, prefab in prefabs.items()
        for problem in check(prefab, registry)
    ]
    if areas is not None:
        problems += _check_areas(areas, prefabs, registry)
    missing: set[str] = set()
    for level in project.all_levels:
        backdrop = level.field("Backdrop")
        if backdrops is not None and backdrop and backdrop not in backdrops:
            problems.append(f"{level.identifier}: no backdrop [{backdrop}]")
        problems += _check_level_area(level, areas)
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


def _check_level_area(level: Level, areas: Areas | None) -> list[str]:
    problems = []
    area, music = level.field("Area"), level.field("Music")
    if areas is not None and area and area not in areas.areas:
        problems.append(f"{level.identifier}: no area [{area}]")
    if music and not NAME.fullmatch(music):
        problems.append(f"{level.identifier}: Music {music!r} is not a stem-set name")
    return problems


def _check_areas(areas: Areas, prefabs: Mapping[str, Prefab], registry: Registry) -> list[str]:
    """Area names and music, and light rules naming a persisted ``Component.field``."""
    problems = []
    for name, spec in areas.areas.items():
        if not NAME.fullmatch(name):
            problems.append(f"area {name!r}: not a lowercase name")
        if spec.music and not NAME.fullmatch(spec.music):
            problems.append(f"area {name}: music {spec.music!r} is not a stem-set name")
    for name, rule in areas.light.items():
        component, _, attribute = rule.partition(".")
        prefab = prefabs.get(name)
        if prefab is None:
            problems.append(f"light {name}: no prefab [{name}]")
        elif component not in prefab.persist:
            problems.append(f"light {name}: prefab {name} does not persist {component}")
        elif component in registry and attribute not in {
            f.name for f in dataclasses.fields(registry[component])
        }:
            problems.append(f"light {name}: {component} has no field {attribute!r}")
    return problems
