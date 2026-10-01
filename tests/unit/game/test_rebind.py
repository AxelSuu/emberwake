from __future__ import annotations

from emberwake.game.actions import Action, default_bindings
from emberwake.game.rebind import primary, rebind, reset


def test_rebind_puts_the_new_input_first_without_duplicates() -> None:
    table: dict[str, list[str]] = {Action.JUMP: ["space", "z", "c"]}
    assert rebind(table, Action.JUMP, "c") is None
    assert table[Action.JUMP] == ["c", "space", "z"]


def test_a_taken_input_moves_and_reports_who_lost_it() -> None:
    table = default_bindings().keys
    assert rebind(table, Action.DASH, "z") == Action.JUMP
    assert primary(table, Action.DASH) == "z"
    assert "z" not in table[Action.JUMP]
    assert table[Action.JUMP] == ["space", "c"]


def test_an_action_left_empty_gets_the_old_input() -> None:
    table: dict[str, list[str]] = {Action.JUMP: ["space"], Action.DASH: ["x"]}
    assert rebind(table, Action.DASH, "space") == Action.JUMP
    assert table == {Action.JUMP: ["x"], Action.DASH: ["space"]}


def test_every_action_stays_bound_and_the_new_input_is_unique() -> None:
    table = default_bindings().keys
    for action in Action:
        for name in ("a", "space", "k", "left"):
            rebind(table, action, name)
            assert all(table[other] for other in Action)
            assert [a for a in Action if name in table[a]] == [action]


def test_reset_restores_defaults_in_place() -> None:
    bindings = default_bindings()
    rebind(bindings.keys, Action.JUMP, "q")
    reset(bindings)
    assert bindings.keys == default_bindings().keys
