"""The gameplay tick: which systems run in which phase."""

from __future__ import annotations

from emberwake.engine.ecs import Schedule
from emberwake.game.player.system import player_system

PHASES = ("input", "logic", "physics", "post", "camera", "render_prep")


def gameplay_schedule() -> Schedule:
    schedule = Schedule(PHASES)
    schedule.add("physics", player_system)
    return schedule
