"""Check the world as a whole: wiring, flags, entrances and what can be reached with what.

Pure functions over the loaded levels and the content files; ``docs/specs/world-validator.md``.
"""

from __future__ import annotations

import contextlib
import math
from collections import defaultdict
from typing import TYPE_CHECKING

from tools.levels.reach import OPEN
from tools.levels.walk import check_reachability
from tools.levels.world import BODY, NEAR, Index, Rules, Thing, index

from emberwake.engine.core.dialogue import DialogueError, flag_of
from emberwake.game.enemies import KINDS
from emberwake.game.flags import HAS, REQUIRES, UNLESS
from emberwake.game.grants import GIVE

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from tools.levels.reach import Cell

    from emberwake.engine.ecs.prefabs import Prefab
    from emberwake.engine.world.ldtk import Project


def check_world(project: Project, prefabs: Mapping[str, Prefab], rules: Rules) -> list[str]:
    """Problems with wiring, flags, entrances and reachability, one line each."""
    world = index(project, prefabs)
    problems = _check_wiring(world)
    problems += _check_encounters(world)
    problems += _check_paths(world)
    problems += _check_flags(world, rules)
    problems += _check_entrances(world)
    problems += check_reachability(world, rules)
    return problems


def _where(thing: Thing) -> str:
    return f"{thing.room} {thing.kind} {thing.iid}"


def _check_wiring(world: Index) -> list[str]:
    known = {thing.iid for thing in world.things}
    return [
        f"{_where(thing)}: targets {iid}, which does not exist"
        for thing in world.things
        for iid in thing.targets()
        if iid not in known
    ]


def _check_encounters(world: Index) -> list[str]:
    """WaveSpawns name an Encounter in their room and an enemy; waves count up from 1."""
    things = {thing.iid: thing for thing in world.things}
    waves: dict[str, set[int]] = {t.iid: set() for t in things.values() if t.kind == "Encounter"}
    problems = []
    for thing in things.values():
        if thing.kind == "Encounter":
            problems += [
                f"{_where(thing)}: Doors names {iid}, which is a {things[iid].kind}, not a Door"
                for iid in thing.entity.values().get("Doors") or []
                if iid in things and things[iid].kind != "Door"
            ]
        if thing.kind != "WaveSpawn":
            continue
        entity = thing.entity
        owner, wave = things.get(entity.values().get("Encounter") or ""), entity.field("Wave", 1)
        if owner is None or owner.kind != "Encounter":
            kind = owner.kind if owner is not None else "missing"
            problems.append(f"{_where(thing)}: Encounter is {kind}, not an Encounter")
        elif owner.room != thing.room:
            problems.append(f"{_where(thing)}: Encounter is in {owner.room}, not in this room")
        else:
            waves[owner.iid].add(wave)
        if wave < 1:
            problems.append(f"{_where(thing)}: Wave {wave} is below 1")
        if (kind := entity.field("Kind")) not in KINDS:
            problems.append(f"{_where(thing)}: Kind {kind!r} is not an enemy ({', '.join(KINDS)})")
    for iid, found in waves.items():
        if not found or found != set(range(1, len(found) + 1)):
            problems.append(f"{_where(things[iid])}: waves {sorted(found)} do not run from 1 up")
    return problems


def _check_paths(world: Index) -> list[str]:
    """A Platform's Path names PathNodes in its room, and names at least one."""
    things = {thing.iid: thing for thing in world.things}
    problems = []
    for thing in things.values():
        if thing.kind != "Platform":
            continue
        path = thing.entity.values().get("Path") or []
        if not path:
            problems.append(f"{_where(thing)}: has no Path")
        for iid in path:
            node = things.get(iid)
            if node is None:
                problems.append(f"{_where(thing)}: Path names {iid}, which does not exist")
            elif node.kind != "PathNode":
                problems.append(f"{_where(thing)}: Path names a {node.kind}, not a PathNode")
            elif node.room != thing.room:
                problems.append(f"{_where(thing)}: Path names a PathNode in {node.room}")
    return problems


def _written(world: Index, rules: Rules) -> set[str]:
    flags = set(rules.shop_flags) | set(rules.code_flags)
    for graph in rules.dialogues.values():
        for node in graph.values():
            flags |= node.set.keys() | node.add.keys()
    for thing in world.things:
        if thing.kind == "SetFlag" and (flag := thing.entity.field("Flag")):
            flags.add(flag)
    return flags


def _given(world: Index, rules: Rules) -> set[str]:
    things = {*rules.abilities, *rules.shop_grants}
    for graph in rules.dialogues.values():
        things |= {n.action.removeprefix(GIVE) for n in graph.values() if n.action.startswith(GIVE)}
    for thing in world.things:
        if thing.kind == "Grant":
            things.add(thing.entity.field("Thing"))
    return things


def _reads(thing: Thing) -> Iterator[tuple[str, str]]:
    fields = [REQUIRES, UNLESS, *(["Condition"] if thing.kind == "FlagSwitch" else [])]
    for name in fields:
        if condition := thing.entity.field(name):
            with contextlib.suppress(DialogueError):
                yield name, flag_of(condition)


def _check_flags(world: Index, rules: Rules) -> list[str]:
    written, given = _written(world, rules), _given(world, rules)
    problems = []
    for thing in world.things:
        if thing.kind == "Grant" and thing.entity.field("Thing") not in rules.grants:
            problems.append(
                f"{_where(thing)}: Thing {thing.entity.field('Thing')!r} is not granted"
            )
        for name, flag in _reads(thing):
            if not flag.startswith(HAS):
                if flag not in written:
                    problems.append(f"{_where(thing)}: {name} reads {flag}, which nothing sets")
                continue
            owned = flag.removeprefix(HAS)
            if owned not in rules.grants:
                problems.append(f"{_where(thing)}: {name} reads {flag}, not in grants.toml")
            elif owned not in given:
                problems.append(f"{_where(thing)}: {name} reads {flag}, which nothing gives")
    return problems


def _passages(world: Index) -> Iterator[tuple[str, str, list[Cell], list[Cell]]]:
    """Runs of an edge two rooms share that is open on both sides: the cells of each room."""
    edges: dict[tuple[str, str, bool], list[tuple[Cell, Cell]]] = defaultdict(list)
    for (x, y), room in world.owner.items():
        for beside, stacked in (((x + 1, y), False), ((x, y + 1), True)):
            other = world.owner.get(beside)
            if other and other != room and _open(world, (x, y)) and _open(world, beside):
                edges[room, other, stacked].append(((x, y), beside))
    for (room, other, stacked), pairs in edges.items():
        axis = 0 if stacked else 1
        pairs.sort(key=lambda pair: pair[0][axis])
        run: list[tuple[Cell, Cell]] = []
        for pair in [*pairs, None]:
            if run and (pair is None or pair[0][axis] != run[-1][0][axis] + 1):
                if stacked or len(run) >= BODY:
                    yield room, other, [a for a, _ in run], [b for _, b in run]
                run = []
            if pair is not None:
                run.append(pair)


def _open(world: Index, cell: Cell) -> bool:
    return world.tiles.get(cell) in OPEN


def _check_entrances(world: Index) -> list[str]:
    problems = []
    for room, other, ours, theirs in _passages(world):
        for here, there, side in ((room, other, ours), (other, room, theirs)):
            near = min(
                (
                    math.hypot(cx - sx, cy - sy)
                    for cx, cy in side
                    for sx, sy in world.starts.get(here, [])
                ),
                default=math.inf,
            )
            if near > NEAR and not world.lab(here):
                left, top = _origin(world, here)
                x, y = side[0]
                problems.append(
                    f"{here}: the way to {there} at tile ({x - left}, {y - top}) has no "
                    f"PlayerStart within {NEAR} tiles"
                )
    return problems


def _origin(world: Index, room: str) -> Cell:
    level = world.levels[room]
    size = level.layer("Collisions").grid_size
    return level.world_x // size, level.world_y // size
