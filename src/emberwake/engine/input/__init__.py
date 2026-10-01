"""Abstract input: actions sampled once per simulation tick, from devices or replays."""

from emberwake.engine.input.mapper import Bindings, InputMapper
from emberwake.engine.input.state import InputState

__all__ = ["Bindings", "InputMapper", "InputState"]
