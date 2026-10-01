from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from emberwake.engine.core.dialogue import (
    DialogueError,
    DialogueRunner,
    holds,
    load_dialogues,
)

if TYPE_CHECKING:
    from pathlib import Path

SCRIPT = """
[npc.start]
text = "hello"
branches = [{ if = "met", goto = "again" }]
set = { met = 1 }
choices = [
    { text = "ask", goto = "shop" },
    { text = "secret", goto = "secret", if = "trust>=3" },
    { text = "bye" },
]

[npc.again]
text = "welcome back"
add = { visits = 1 }
next = "start_menu"

[npc.start_menu]
text = "what now"
choices = [{ text = "ask", goto = "shop" }, { text = "bye" }]

[npc.shop]
text = "buy something"
action = "shop"
next = "thanks"

[npc.thanks]
text = "thanks"

[npc.secret]
text = "psst"
"""


@pytest.fixture
def graph(tmp_path: Path):
    path = tmp_path / "d.toml"
    path.write_text(SCRIPT)
    return load_dialogues(path)["npc"]


@pytest.mark.parametrize(
    ("condition", "flags", "expected"),
    [
        ("a", {"a": 1}, True),
        ("a", {}, False),
        ("!a", {}, True),
        ("!a", {"a": 2}, False),
        ("n>=3", {"n": 3}, True),
        ("n>=3", {"n": 2}, False),
        ("n<3", {}, True),
        ("n == 2", {"n": 2}, True),
        ("n!=2", {"n": 2}, False),
        ("n>1", {"n": 2}, True),
        ("n<=0", {}, True),
    ],
)
def test_conditions(condition: str, flags: dict[str, int], expected: bool) -> None:
    assert holds(condition, flags) is expected


def test_bad_conditions_are_errors() -> None:
    with pytest.raises(DialogueError):
        holds("n >= x", {})


def test_first_visit_sets_flags_and_offers_choices(graph) -> None:
    flags: dict[str, int] = {}
    run = DialogueRunner(graph, flags)
    assert run.text == "hello"
    assert flags == {"met": 1}
    assert [c.text for c in run.choices] == ["ask", "bye"]


def test_a_condition_unlocks_a_choice(graph) -> None:
    run = DialogueRunner(graph, {"trust": 3})
    assert [c.text for c in run.choices] == ["ask", "secret", "bye"]
    run.advance(1)
    assert run.text == "psst"
    run.advance()
    assert run.finished


def test_branches_pick_the_returning_greeting(graph) -> None:
    flags = {"met": 1}
    run = DialogueRunner(graph, flags)
    assert run.text == "welcome back"
    assert flags["visits"] == 1
    run.advance()
    assert run.text == "what now"


def test_actions_are_reported_once(graph) -> None:
    run = DialogueRunner(graph, {})
    run.advance(0)
    assert run.take_actions() == ["shop"]
    assert run.take_actions() == []
    run.advance()
    assert run.text == "thanks"
    run.advance()
    assert run.finished


def test_a_choice_without_a_target_ends_the_conversation(graph) -> None:
    run = DialogueRunner(graph, {})
    run.advance(1)
    assert run.finished


def test_choosing_wrongly_is_an_error(graph) -> None:
    run = DialogueRunner(graph, {})
    with pytest.raises(DialogueError):
        run.advance()
    with pytest.raises(DialogueError):
        run.advance(9)


def test_advancing_a_finished_conversation_does_nothing(graph) -> None:
    run = DialogueRunner(graph, {})
    run.advance(1)
    run.advance()
    assert run.finished


def test_broken_scripts_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('[a.start]\ntext = "x"\nnext = "nowhere"\n')
    with pytest.raises(DialogueError, match="unknown node"):
        load_dialogues(path)
    path.write_text('[a.other]\ntext = "x"\n')
    with pytest.raises(DialogueError, match="start"):
        load_dialogues(path)


def test_cyclic_branches_do_not_hang(tmp_path: Path) -> None:
    path = tmp_path / "loop.toml"
    path.write_text(
        '[a.start]\nbranches = [{ goto = "b" }]\n[a.b]\nbranches = [{ goto = "start" }]\n'
    )
    graph = load_dialogues(path)["a"]
    with pytest.raises(DialogueError, match="too many"):
        DialogueRunner(graph, {})
