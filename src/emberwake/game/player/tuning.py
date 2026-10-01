"""Movement tuning. Defaults mirror docs/specs/player-movement.md; content/player.toml overrides."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerTuning:
    width: float = 10
    height: float = 20
    max_run: float = 180
    run_accel: float = 2000
    run_decel: float = 800
    air_mult: float = 0.65
    gravity: float = 1800
    max_fall: float = 320
    apex_threshold: float = 80
    apex_gravity_mult: float = 0.5
    jump_speed: float = 210
    jump_h_boost: float = 80
    var_jump: int = 12
    jump_cut: float = 0.5
    coyote: int = 6
    jump_buffer: int = 6
    corner_correction: int = 6
    drop_through: int = 8
    wall_slide_max: float = 80
    wall_jump_speed: float = 260
    wall_jump_lock: int = 10
    wall_jump_reach: float = 3
    dash_speed: float = 480
    dash_end_speed: float = 320
    dash_end_up_mult: float = 0.75
    dash_ticks: int = 9
    dash_charges: int = 1
    hazard_margin: float = 2
