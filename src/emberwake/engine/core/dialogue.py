"""Branching dialogue from TOML, run against a dictionary of integer flags.

A file holds graphs; each graph is a table of nodes::

    [tinker.start]
    text = "dialogue.tinker.hello"          # a string key, so it is translated
    branches = [{ if = "met", goto = "again" }]   # jump on entering when a condition holds
    set = { met = 1 }                        # flags to set or add to on entering
    choices = [
        { text = "dialogue.tinker.shop", goto = "shop" },
        { text = "dialogue.tinker.secret", goto = "secret", if = "trust>=3" },
    ]

    [tinker.shop]
    text = "dialogue.tinker.shop_line"
    action = "shop"                          # the game decides what an action does
    next = "start"                           # continue here (no choices), or end if absent

Conditions are a flag name (non-zero), ``!name``, or ``name`` with ``>=``, ``<=``, ``>``, ``<``,
``==`` or ``!=`` and a number. Missing flags count as 0.
"""

from __future__ import annotations

import operator
import re
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

START = "start"
MAX_JUMPS = 32
"""Branches followed in a row before giving up, so a cycle of conditions cannot hang."""

_COMPARE: dict[str, Callable[[int, int], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
}
_CONDITION = re.compile(r"^\s*(!?)\s*([A-Za-z_][\w.]*)\s*(?:(>=|<=|==|!=|>|<)\s*(-?\d+))?\s*$")


class DialogueError(ValueError):
    """A script that cannot be loaded or run."""


def holds(condition: str, flags: Mapping[str, int]) -> bool:
    """Whether `condition` is true for `flags`."""
    match = _CONDITION.match(condition)
    if match is None:
        raise DialogueError(f"bad condition {condition!r}")
    negate, name, op, number = match.groups()
    value = flags.get(name, 0)
    if op:
        return _COMPARE[op](value, int(number))
    return (value == 0) if negate else (value != 0)


def flag_of(condition: str) -> str:
    """The flag a condition reads: ``"trust>=3"`` -> ``"trust"``."""
    match = _CONDITION.match(condition)
    if match is None:
        raise DialogueError(f"bad condition {condition!r}")
    return match.group(2)


@dataclass(slots=True)
class Choice:
    """An option the player can pick."""

    text: str
    goto: str = ""
    """Node to go to; empty ends the conversation."""
    if_: str = field(default="", metadata={"serde_key": "if"})
    """Condition for the choice to be offered."""


@dataclass(slots=True)
class Branch:
    """A jump taken on entering a node when its condition holds."""

    goto: str
    if_: str = field(default="", metadata={"serde_key": "if"})


@dataclass(slots=True)
class Node:
    """One line of dialogue and what follows it."""

    text: str = ""
    choices: list[Choice] = field(default_factory=list)
    branches: list[Branch] = field(default_factory=list)
    set: dict[str, int] = field(default_factory=dict)
    add: dict[str, int] = field(default_factory=dict)
    action: str = ""
    next: str = ""


type Graph = dict[str, Node]


def flags_used(graph: Graph) -> set[str]:
    """Every flag the graph reads in a condition or writes with `set` or `add`."""
    names: set[str] = set()
    for node in graph.values():
        names |= node.set.keys() | node.add.keys()
        conditions = [c.if_ for c in node.choices] + [b.if_ for b in node.branches]
        names |= {flag_of(condition) for condition in conditions if condition}
    return names


def load_dialogues(path: Path) -> dict[str, Graph]:
    """Parse a TOML file of graphs and check every jump lands on a node."""
    data = from_data(dict[str, Graph], tomllib.loads(path.read_text(encoding="utf-8")))
    for name, graph in data.items():
        if START not in graph:
            raise DialogueError(f"{name}: no {START!r} node")
        for node_id, node in graph.items():
            targets = [node.next, *(c.goto for c in node.choices), *(b.goto for b in node.branches)]
            for target in targets:
                if target and target not in graph:
                    raise DialogueError(f"{name}.{node_id}: jumps to unknown node {target!r}")
    return data


class DialogueRunner:
    """Walks a graph. Flags are shared with the caller, so effects persist in a save."""

    def __init__(self, graph: Graph, flags: dict[str, int]) -> None:
        self.graph = graph
        self.flags = flags
        self.node_id = ""
        self.finished = False
        self.actions: list[str] = []
        self._enter(START)

    @property
    def node(self) -> Node:
        """The current node."""
        return self.graph[self.node_id]

    @property
    def text(self) -> str:
        """The string key of the current line."""
        return self.node.text

    @property
    def choices(self) -> list[Choice]:
        """The choices on offer, those whose conditions hold."""
        return [c for c in self.node.choices if not c.if_ or holds(c.if_, self.flags)]

    def advance(self, choice: int | None = None) -> None:
        """Move on: pick the `choice`-th offered choice, or continue when there are none."""
        if self.finished:
            return
        offered = self.choices
        if offered:
            if choice is None or not 0 <= choice < len(offered):
                raise DialogueError("choose one of the offered choices")
            target = offered[choice].goto
        else:
            target = self.node.next
        if target:
            self._enter(target)
        else:
            self.finished = True

    def take_actions(self) -> list[str]:
        """The actions of nodes entered since the last call."""
        taken, self.actions = self.actions, []
        return taken

    def _enter(self, node_id: str) -> None:
        for _ in range(MAX_JUMPS):
            node = self.graph[node_id]
            taken = (b.goto for b in node.branches if not b.if_ or holds(b.if_, self.flags))
            jump = next(taken, "")
            if not jump:
                break
            node_id = jump
        else:
            raise DialogueError(f"too many branches from {node_id!r}")
        self.node_id = node_id
        node = self.graph[node_id]
        self.flags.update(node.set)
        for name, amount in node.add.items():
            self.flags[name] = self.flags.get(name, 0) + amount
        if node.action:
            self.actions.append(node.action)
