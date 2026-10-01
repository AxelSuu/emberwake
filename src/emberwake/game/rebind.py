"""Changing one binding without leaving an action unbound or a key doing two things."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.game.actions import Action, default_bindings

if TYPE_CHECKING:
    from emberwake.engine.input import Bindings


def primary(table: dict[str, list[str]], action: Action) -> str:
    """The first input bound to `action`, or an empty string."""
    inputs = table.get(action, [])
    return inputs[0] if inputs else ""


def rebind(table: dict[str, list[str]], action: Action, new: str) -> Action | None:
    """Make `new` the first input of `action` in the ``Bindings.keys`` `table`.

    An input already bound elsewhere moves here. An action that would be left with nothing gets
    the input `action` just gave up (a swap). Returns the action that lost `new`, if any.
    """
    old = primary(table, action)
    taken: Action | None = None
    given = False
    for other in Action:
        if other == action or new not in table.get(other, []):
            continue
        taken = other
        kept = [i for i in table[other] if i != new]
        given = given or (not kept and bool(old))
        table[other] = kept or ([old] if old else [])
    dropped = (new, old) if given else (new,)
    table[action] = [new, *(i for i in table.get(action, []) if i not in dropped)]
    return taken


def reset(bindings: Bindings) -> None:
    """Restore the default keys in place."""
    defaults = default_bindings()
    bindings.keys = defaults.keys
