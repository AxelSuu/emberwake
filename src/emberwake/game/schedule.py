"""The gameplay tick: which systems run in which phase."""

from __future__ import annotations

from emberwake.engine.ecs import Schedule
from emberwake.game.beacons import beacon_system
from emberwake.game.breakables import breakable_system, crumble_system, loose_ember_system
from emberwake.game.cinder import cinder_system
from emberwake.game.combat import combat_system
from emberwake.game.dialogue import npc_system
from emberwake.game.encounters import encounter_system, lock_system
from emberwake.game.enemies import enemy_system
from emberwake.game.flags import flag_system, gate_system
from emberwake.game.flares import flare_system
from emberwake.game.grants import grant_system
from emberwake.game.interact import interact_system, pickup_system, plate_system, trigger_system
from emberwake.game.lamps import lamp_system
from emberwake.game.light import ember_system, lightform_system
from emberwake.game.lore import echo_system
from emberwake.game.lost_lights import lost_light_system
from emberwake.game.player.kindle import kindle_system
from emberwake.game.player.swing import strike_system, swing_system
from emberwake.game.player.system import player_system
from emberwake.game.render.sprites import sprite_system
from emberwake.game.rooms import room_system
from emberwake.game.signals import door_system, signal_system
from emberwake.game.switches import bell_system, brazier_system, photocell_system
from emberwake.game.trials import goal_system, trial_door_system

PHASES = ("input", "logic", "physics", "post", "camera", "render_prep")
POST = (
    room_system,
    trigger_system,
    flag_system,
    lost_light_system,
    cinder_system,
    plate_system,
    pickup_system,
    grant_system,
    combat_system,
    strike_system,
    breakable_system,
    crumble_system,
    loose_ember_system,
    lamp_system,
    goal_system,
    flare_system,
    lightform_system,
    ember_system,
    brazier_system,
    bell_system,
    photocell_system,
    encounter_system,
    gate_system,
    signal_system,
    lock_system,
    door_system,
)
"""In order: rooms may spawn or despawn, then contacts and flags, combat and what the swing struck,
the switches light and bells drive, encounters, the world's gates once the facts settle, signals,
the doors encounters shut, what signals drive."""


def gameplay_schedule() -> Schedule:
    schedule = Schedule(PHASES)
    schedule.add("logic", interact_system)
    schedule.add("logic", swing_system)
    schedule.add("logic", kindle_system)
    schedule.add("logic", beacon_system)
    schedule.add("logic", enemy_system)
    schedule.add("logic", npc_system)
    schedule.add("logic", echo_system)
    schedule.add("logic", trial_door_system)
    schedule.add("physics", player_system)
    for system in POST:
        schedule.add("post", system)
    schedule.add("render_prep", sprite_system)
    return schedule
