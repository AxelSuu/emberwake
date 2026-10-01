# Player movement

**Milestone:** M1  **Status:** done  **Issues:** #7, #8

## Goal
Movement that feels tight and fair: instant intent, readable arcs and forgiving timing windows,
so failure always feels like the player's own mistake.

## Model
- The hitbox is an axis-aligned box. The sprite is drawn bottom-centred on it and never collides.
- One simulation tick is 1/60 s. Speeds are px/s, accelerations px/s², windows are whole ticks.
- Collision is resolved by `engine.physics` (x first, then y, sub-stepped, see #5).
- The controller is a pure function of (player, input, grid, tuning). It returns events such as
  `Jumped`, `Landed`, `Dashed` and `Died`. Feedback (shake, squash, particles) reacts to those
  events and never feeds back into movement.

## States

```
          jump / fall                      push into wall while falling
 GROUND ───────────────► AIR ◄────────────────────────────────► WALL_SLIDE
   ▲  land                │ ▲                     release / leave wall
   └──────────────────────┘ │ dash ends
                            │
     dash (any state, needs a charge)  ──► DASH ──┘
```

## Rules

**Running.** Horizontal intent is right minus left. Velocity approaches `intent * max_run` at
`run_accel`; above `max_run` in the same direction it slows at `run_decel` instead, so dash
momentum is kept briefly. In the air both rates are multiplied by `air_mult`.

**Gravity.** Vertical velocity approaches `max_fall` at `gravity`. While jump is held and
`|vy| < apex_threshold`, gravity is multiplied by `apex_gravity_mult` (apex hang).

**Jumping.** A jump starts when jump was pressed within the last `jump_buffer` ticks and the
player is grounded or left the ground at most `coyote` ticks ago. The jump sets
`vy = -jump_speed` and adds `jump_h_boost * intent` to `vx`. For `var_jump` ticks, holding jump
keeps `vy` at most `-jump_speed`; releasing early multiplies upward velocity by `jump_cut` once.

**Corner correction.** When rising into a ceiling, the player is shifted up to
`corner_correction` px sideways (movement direction first) if that clears the ceiling.

**One-way platforms.** Solid only from above. Down + jump while standing on one drops through it.

**Wall slide.** In the air, falling, and pushing into a wall: fall speed approaches
`wall_slide_max` (at the gravity rate, so a fast fall eases into the slide) and stays there.

**Wall jump.** Jump pressed in the air, without coyote time, within `wall_jump_reach` px of a
wall: `vx = wall_jump_speed` away from the wall, `vy = -jump_speed`, and horizontal intent is
forced away from the wall for `wall_jump_lock` ticks.

**Dash.** Dash pressed with a charge left: direction is the 8-way intent (facing if none),
normalized. For `dash_ticks` ticks velocity is `direction * dash_speed`, with no gravity. When the
dash ends, velocity becomes `direction * dash_end_speed` (upward part times `dash_end_up_mult`).
Charges refill on landing once the dash has ended. Starting a dash emits `Dashed`, and the scene
answers with a short hitstop.

**Death.** Touching a hazard tile (hitbox shrunk by `hazard_margin`) or falling below the room
emits `Died`. The scene respawns the player at the room's `PlayerStart`.

## Tuning parameters

Defaults live in `content/feel.toml` (`[player]`); F5 reloads them in `--dev`. Values are Celeste's, doubled
for our 16 px tiles.

| Name | Default | Unit | Notes |
|---|---|---|---|
| `width`, `height` | 10, 20 | px | hitbox |
| `max_run` | 180 | px/s | |
| `run_accel` | 2000 | px/s² | |
| `run_decel` | 800 | px/s² | above max speed |
| `air_mult` | 0.65 | | multiplies accel and decel in the air |
| `gravity` | 1800 | px/s² | |
| `max_fall` | 320 | px/s | |
| `apex_threshold` | 80 | px/s | |
| `apex_gravity_mult` | 0.5 | | |
| `jump_speed` | 210 | px/s | |
| `jump_h_boost` | 80 | px/s | |
| `var_jump` | 12 | ticks | |
| `jump_cut` | 0.5 | | on early release |
| `coyote` | 6 | ticks | |
| `jump_buffer` | 6 | ticks | |
| `corner_correction` | 6 | px | |
| `drop_through` | 8 | ticks | one-way platforms ignored after dropping |
| `wall_slide_max` | 80 | px/s | |
| `wall_jump_speed` | 260 | px/s | |
| `wall_jump_lock` | 10 | ticks | |
| `wall_jump_reach` | 3 | px | |
| `dash_speed` | 480 | px/s | |
| `dash_end_speed` | 320 | px/s | |
| `dash_end_up_mult` | 0.75 | | |
| `dash_ticks` | 9 | ticks | |
| `dash_charges` | 1 | | |
| `hazard_margin` | 2 | px | |

## Acceptance criteria
- [x] Holding right from standstill reaches `max_run` within 6 ticks and never exceeds it.
- [x] A held full jump peaks between 3.5 and 4.5 tiles. A one-tick tap peaks below 2 tiles.
- [x] A running full jump clears a 6-tile gap.
- [x] Jump pressed up to `coyote` ticks after walking off a ledge still jumps; one tick later it does not.
- [x] Jump pressed up to `jump_buffer` ticks before landing jumps on the landing tick.
- [x] Rising into a ceiling edge overlapping by at most `corner_correction` px slides past it.
- [x] Wall slide slows the fall to `wall_slide_max` within a few ticks and then never exceeds it.
- [x] A wall jump moves away from the wall and gains height.
- [x] A horizontal dash travels about 4.5 tiles, and the charge refills only after landing.
- [x] Down + jump on a one-way platform drops through it. Jumping up through one works.
- [x] Touching spikes or falling out of the room emits `Died`.

## Tests
`tests/unit/game/test_player.py`: scenario tests that feed per-tick action sets (the same format
replays use) into the controller on small ASCII rooms.
