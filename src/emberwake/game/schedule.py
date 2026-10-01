"""The gameplay tick: which systems run in which phase."""

from __future__ import annotations

from emberwake.engine.ecs import Schedule
from emberwake.game.interact import interact_system, pickup_system, plate_system, trigger_system
from emberwake.game.player.system import player_system
from emberwake.game.render.sprites import sprite_system
from emberwake.game.rooms import room_system
from emberwake.game.signals import door_system, signal_system

PHASES = ("input", "logic", "physics", "post", "camera", "render_prep")
POST = (room_system, trigger_system, plate_system, pickup_system, signal_system, door_system)
"""In order: rooms may spawn or despawn, then contacts, then signals, then what they drive."""


def gameplay_schedule() -> Schedule:
    schedule = Schedule(PHASES)
    schedule.add("logic", interact_system)
    schedule.add("physics", player_system)
    for system in POST:
        schedule.add("post", system)
    schedule.add("render_prep", sprite_system)
    return schedule
