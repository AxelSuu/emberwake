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


INTERACT_KEYS = ["up", "w", "e"]
INTERACT_BUTTONS = ["y", "dpad_up"]


def default_bindings() -> Bindings:
    return Bindings(
        keys={
            Action.LEFT: ["left", "a"],
            Action.RIGHT: ["right", "d"],
            Action.UP: ["up", "w"],
            Action.DOWN: ["down", "s"],
            Action.JUMP: ["space", "z", "c"],
            Action.DASH: ["x", "left shift", "k"],
            Action.INTERACT: INTERACT_KEYS,
        },
        buttons={
            Action.LEFT: ["dpad_left", "leftx-"],
            Action.RIGHT: ["dpad_right", "leftx+"],
            Action.UP: ["dpad_up", "lefty-"],
            Action.DOWN: ["dpad_down", "lefty+"],
            Action.JUMP: ["a"],
            Action.DASH: ["x", "b", "rightshoulder"],
            Action.INTERACT: INTERACT_BUTTONS,
        },
    )
