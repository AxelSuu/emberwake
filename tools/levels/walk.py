"""Reachability: grow what the player can reach and do from the start room until nothing changes."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tools.levels.reach import Cell, Moves, reach

from emberwake.engine.core.dialogue import DialogueError, flag_of, holds
from emberwake.engine.physics import Tile
from emberwake.game.flags import HAS, REQUIRES
from emberwake.game.grants import GIVE

if TYPE_CHECKING:
    from collections.abc import Collection

    from tools.levels.world import Index, Rules, Thing


type Known = dict[str, int]


@dataclass(slots=True)
class Settled:
    """What the player has, knows and can reach once nothing more unlocks."""

    abilities: set[str]
    rooms: set[str]
    opened: set[str]


def _holds(condition: str, facts: Known, wide: set[str]) -> bool:
    try:
        return flag_of(condition) in wide or holds(condition, facts)
    except DialogueError:
        return False


class Walk:
    """Grows what the player can do from the start room until nothing changes."""

    def __init__(self, world: Index, rules: Rules) -> None:
        self.world, self.rules = world, rules
        self.doors = {t.iid: t for t in world.things if t.kind == "Door"}
        self.crates = [t for t in world.things if t.kind == "PushCrate"]
        self.sources: dict[str, list[Thing]] = defaultdict(list)
        by_iid = {t.iid: t for t in world.things}
        for thing in world.things:
            for target in thing.targets():
                if target in by_iid:
                    self.sources[target].append(thing)
        self.memo: dict[tuple[frozenset[str], frozenset[str]], Settled] = {}
        self.reaches: dict[tuple[frozenset[str], Moves], set[Cell]] = {}
        self.tiles = dict(world.tiles)
        for thing in world.things:
            if thing.kind == "Lightform":
                self.tiles.update(dict.fromkeys(thing.cells, Tile.ONE_WAY))

    def settle(self, extra: Collection[str] = (), forced: Collection[str] = ()) -> Settled:
        key = frozenset(extra), frozenset(forced)
        if key not in self.memo:
            self.memo[key] = self._settle(*key)
        return self.memo[key]

    def _settle(self, extra: Collection[str], forced: Collection[str]) -> Settled:
        world = self.world
        abilities = {*self.rules.abilities, *extra}
        facts: Known = {HAS + name: 1 for name in abilities}
        wide: set[str] = set()
        opened = set(forced)
        while True:
            before = (
                frozenset(abilities),
                tuple(sorted(facts.items())),
                frozenset(opened),
                len(wide),
            )
            cells = self._cells(opened, abilities)
            reached = [t for t in world.things if t.cells & cells and self._present(t, facts, wide)]
            items: Counter[str] = Counter()
            for thing in reached:
                self._effects(thing, abilities, items, facts, wide)
            for name, count in items.items():
                facts[HAS + name] = max(
                    facts.get(HAS + name, 0), min(self.rules.grants[name].max, count)
                )
            for door in self.doors.values():
                if self._opens(door, reached, facts, wide):
                    opened.add(door.iid)
            after = (
                frozenset(abilities),
                tuple(sorted(facts.items())),
                frozenset(opened),
                len(wide),
            )
            if after == before:
                rooms = {world.owner[cell] for cell in cells if cell in world.owner}
                return Settled(abilities, rooms, opened)

    def _cells(self, opened: Collection[str], abilities: Collection[str]) -> set[Cell]:
        moves = Moves().with_abilities(abilities)
        key = frozenset(opened), moves
        if key not in self.reaches:
            tiles = dict(self.tiles)
            for iid, door in self.doors.items():
                if iid not in opened:
                    tiles.update(dict.fromkeys(door.cells, Tile.SOLID))
            starts = self.world.starts.get(self.rules.start, [])
            self.reaches[key] = reach(tiles, starts, moves)
        return self.reaches[key]

    def _present(self, thing: Thing, facts: Known, wide: set[str]) -> bool:
        requires = thing.entity.field(REQUIRES)
        return not requires or _holds(requires, facts, wide)

    def _opens(self, door: Thing, reached: list[Thing], facts: Known, wide: set[str]) -> bool:
        entity = door.entity
        if entity.field("Invert"):
            return True

        def on(source: Thing) -> bool:
            if source.kind == "FlagSwitch":
                condition = source.entity.field("Condition")
                return bool(condition) and _holds(condition, facts, wide)
            if source.kind == "PressurePlate":
                return source in reached or any(
                    crate.room == source.room and crate in reached for crate in self.crates
                )
            return source in reached

        states = [on(source) for source in self.sources[door.iid]]
        return all(states) and bool(states) if entity.field("Mode") == "all" else any(states)

    def _effects(
        self, thing: Thing, abilities: set[str], items: Counter[str], facts: Known, wide: set[str]
    ) -> None:
        entity = thing.entity
        if thing.kind == "Grant":
            self._give(entity.field("Thing"), entity.field("Count", 1), abilities, items, facts)
        elif thing.kind == "SetFlag" and (flag := entity.field("Flag")):
            if entity.field("Mode") == "add":
                wide.add(flag)
            facts[flag] = max(facts.get(flag, 0), entity.field("Value", 1))
        elif thing.prefab is not None and (npc := thing.prefab.components.get("Npc")):
            for node in self.rules.dialogues.get(npc.get("dialogue", ""), {}).values():
                wide.update(node.add)
                for flag, value in (node.set | node.add).items():
                    facts[flag] = max(facts.get(flag, 0), value)
                if node.action.startswith(GIVE):
                    self._give(node.action.removeprefix(GIVE), 1, abilities, items, facts)
                elif node.action == "shop":
                    for flag in self.rules.shop_flags:
                        facts[flag] = max(facts.get(flag, 0), 1)

    def _give(
        self, name: str, count: int, abilities: set[str], items: Counter[str], facts: Known
    ) -> None:
        spec = self.rules.grants.get(name)
        if spec is not None and spec.kind == "ability":
            abilities.add(name)
            facts[HAS + name] = 1
        elif spec is not None:
            items[name] += count


def _granted_in(world: Index, rules: Rules, ability: str) -> str:
    rooms = {
        t.room
        for t in world.things
        if (t.kind == "Grant" and t.entity.field("Thing") == ability)
        or (
            t.prefab is not None
            and (npc := t.prefab.components.get("Npc"))
            and any(
                n.action == GIVE + ability
                for n in rules.dialogues.get(npc.get("dialogue", ""), {}).values()
            )
        )
    }
    return ", ".join(sorted(rooms)) or "nowhere"


def _why(walk: Walk, room: str, base: Settled) -> str:
    """What would make `room` reachable: one more ability, one open door, or no way at all."""
    rules = walk.rules
    missing = sorted(
        a for a, s in rules.grants.items() if s.kind == "ability" and a not in base.abilities
    )
    for ability in missing:
        if room in walk.settle(extra=[ability]).rooms:
            return f"needs {ability}, granted in {_granted_in(walk.world, rules, ability)}"
    for iid, door in walk.doors.items():
        if iid not in base.opened and room in walk.settle(forced=[iid]).rooms:
            sources = [s.iid for s in walk.sources[iid]]
            return f"is behind Door {iid} in {door.room}, whose sources {sources} cannot be used"
    if room in walk.settle(extra=missing, forced=walk.doors).rooms:
        return "needs more than one ability or door"
    return "has no open way in"


def check_reachability(world: Index, rules: Rules) -> list[str]:
    start = rules.start
    if start not in world.levels or world.lab(start):
        return []
    if not world.starts.get(start):
        return [f"{start}: the start room has no PlayerStart"]
    walk = Walk(world, rules)
    base = walk.settle()
    return [
        f"{room}: not reachable from {start}, it {_why(walk, room, base)}"
        for room in world.levels
        if room not in base.rooms and not world.lab(room) and room not in rules.trials
    ]
