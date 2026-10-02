"""Signposts and Echoes: text in the world, and ghosts that replay a lamplighter's last moments.

See ``docs/specs/lore-and-lost-lights.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.game.interact import overlap, player_body
from emberwake.game.rebind import labels

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.ecs import World


@component
@dataclass(slots=True)
class Sign:
    """Shows the string ``sign.<text>`` while the player is within `reach` px."""

    text: str = ""
    reach: float = 28.0


@dataclass(frozen=True, slots=True)
class Speech:
    """A line to show above a point in the world."""

    x: float
    y: float
    text: str


def sign_text(t: Callable[..., str], sign: Sign, keys: dict[str, list[str]]) -> str:
    """The sign's string with ``{jump}`` and friends replaced by the keys now bound, as ``[Z]``."""
    return t(f"sign.{sign.text}", **{action: f"[{key}]" for action, key in labels(keys).items()})


def speeches(world: World, t: Callable[..., str], keys: dict[str, list[str]]) -> list[Speech]:
    """What is being said now: each sign the player stands near."""
    player = player_body(world)
    if player is None:
        return []
    return [
        Speech(body.center_x, body.y, sign_text(t, sign, keys))
        for _, body, sign in world.query(Body, Sign)
        if overlap(body, player, sign.reach)
    ]
