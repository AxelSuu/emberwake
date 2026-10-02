"""The game's input actions and their default bindings."""

from __future__ import annotations

from enum import StrEnum

from emberwake.engine.input import Bindings


class Action(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    JUMP = "jump"
    DASH = "dash"
    INTERACT = "interact"
    FLARE = "flare"
    SWING = "swing"


INTERACT_KEYS = ["up", "w", "e"]
FLARE_KEYS = ["f", "q"]
SWING_KEYS = ["c", "j"]
OLD_JUMP_KEYS = ["space", "z", "c"]
"""Jump's defaults before the swing took C."""


def default_bindings() -> Bindings:
    return Bindings(
        keys={
            Action.LEFT: ["left", "a"],
            Action.RIGHT: ["right", "d"],
            Action.UP: ["up", "w"],
            Action.DOWN: ["down", "s"],
            Action.JUMP: ["space", "z"],
            Action.DASH: ["x", "left shift", "k"],
            Action.INTERACT: INTERACT_KEYS,
            Action.FLARE: FLARE_KEYS,
            Action.SWING: SWING_KEYS,
        },
    )
