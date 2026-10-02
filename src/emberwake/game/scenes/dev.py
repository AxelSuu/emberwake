"""Developer overlays (``--dev``): warp to any room, toggle flags. Not translated."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.ui import Button, Label, Panel, ScrollList, Toggle, Widget
from emberwake.game.scenes.overlay import Overlay

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from emberwake.game.context import GameContext

VISIBLE_ROWS = 14


class WarpScene(Overlay):
    """Pick a room; the overlay closes and `on_pick` moves the player there."""

    def __init__(
        self,
        ctx: GameContext,
        rooms: Sequence[str],
        current: str,
        on_pick: Callable[[str], None],
    ) -> None:
        self.on_pick = on_pick
        buttons = [Button(room, lambda room=room: self._pick(room)) for room in rooms]
        self.list = ScrollList(buttons, VISIBLE_ROWS)
        if current in rooms:
            self.list.index = list(rooms).index(current)
        super().__init__(ctx, Panel([Label("Warp to room (F6)"), self.list]), self._back)

    def _pick(self, room: str) -> None:
        self.manager.pop()
        self.on_pick(room)

    def _back(self) -> None:
        self.manager.pop()


class FlagsScene(Overlay):
    """Toggle abilities and flags of the running game in place: on sets 1, off removes the flag."""

    def __init__(
        self,
        ctx: GameContext,
        flags: dict[str, int],
        names: Iterable[str],
        abilities: list[str] | None = None,
        known_abilities: Iterable[str] = (),
    ) -> None:
        self.flags = flags
        self.abilities = abilities if abilities is not None else []
        rows: list[Widget] = [
            Toggle(f"ability: {name}", name in self.abilities, lambda on, n=name: self._own(n, on))
            for name in sorted({*known_abilities, *self.abilities})
        ]
        rows += [
            Toggle(self._label(name), flags.get(name, 0) != 0, lambda on, n=name: self._set(n, on))
            for name in sorted({*names, *flags})
        ]
        self.list = ScrollList(rows, VISIBLE_ROWS)
        super().__init__(ctx, Panel([Label("Flags (F7)"), self.list]), self._back)

    def _label(self, name: str) -> str:
        value = self.flags.get(name, 0)
        return f"{name} = {value}" if value not in (0, 1) else name

    def _own(self, ability: str, on: bool) -> None:
        if on and ability not in self.abilities:
            self.abilities.append(ability)
        elif not on and ability in self.abilities:
            self.abilities.remove(ability)

    def _set(self, name: str, on: bool) -> None:
        if on:
            self.flags[name] = self.flags.get(name, 0) or 1
        else:
            self.flags.pop(name, None)

    def _back(self) -> None:
        self.manager.pop()
