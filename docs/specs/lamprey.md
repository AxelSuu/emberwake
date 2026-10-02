# The Lamprey

**Milestone:** M9  **Status:** done  **Issue:** #51

## Goal
The Quarter's boss: a skeletal eel in the flooded Cistern that hunts the brightest light. The
player learns to bait it into stone, to keep the lamps burning while it eats them, and to light
the photocells it cracks open, which drains the arena for a last stand on the floor. It is the
Quarter's test of everything taught: flares, lamps, photocells, the pogo and the swing. Its
reveal and the Great Lamp are story beats (#138), not part of this; it only publishes an event
and sets a flag when it dies.

## Behavior

A `Lamprey` entity (`game/lamprey.py`, tree in `game/lamprey_tree.py`): a head with a `Body`,
`Health`, `Hurtbox`, a contact `Hitbox` and a `Guard`, placed at the water line of its arena. It
is a boss, so its brain is a behavior tree (`engine.core.bt`, one tree per Lamprey) instead of an
`Fsm`. The tree is ticked by `lamprey_system` once per step, while the player is inside the
arena (the Lamprey's room). Its lure is a `LightSource` that glows through the water.

### Phases
Hit points are split in three equal parts; the phase follows the points left: 1 above two
thirds, 2 above one third, then 3. A phase change aborts what the tree is doing and starts the
new phase from its first step. Phases only go forward.

1. **Lure.** A cycle of *emerge* (swim under the brightest light, rise), *stalk* (the lure
   sways, the head follows the light), *lunge* (a straight dash at the light that goes on past
   it) and *dive*. The lunge ends at the first stone it touches, or after `lunge_range` px.
   Stone: it is *stunned* for `stun_time`. Air: a short *recover*. A stunned Lamprey has no
   armor and does not hurt on contact; otherwise it is armored on every side. A lunge that
   reaches the player hurts.
2. **Dark water.** A cycle of *swim* (submerged, toward the nearest lit lamp, else the player),
   *warn* (ripples and the lure bobbing), *breach* (an arc out of the water over the target's
   platform, `breach_span` px to each side) and *dive*. A breach snuffs every lit lamp it
   passes within `snuff_reach` px. Armored from the sides always; the back is open from above
   while it breaches, so a down swing or pogo from over it hurts. Submerged it cannot be hit.
3. **Drain.** *3a, flooded:* the phase 1 cycle with the armor up even when stunned, and with
   its lure out. A lunge that passes through a sealed photocell breaks its casing, so the
   photocell reads light from then on. When every photocell of the arena is lit at once, the
   Lamprey sets `lamprey_drained`: the water is gone (a door powered by a FlagSwitch on that flag
   becomes the floor), and it slumps onto it. *3b, drained:* *thrash* (slides at the player on
   the floor, armored, hurting) alternating with *gasp* (stopped, open, harmless) for
   `gasp_time`: the short windows to hit its head.

### Bait
It aims at the brightest light in the arena: lit lamps, flares, lit braziers and beacons, and
the player's own lantern, each weighed (`bait_*`) and scaled by its strength. Ties go to the
nearest. A flare thrown next to a wall makes the lunge end in that wall. With nothing else
lit it hunts the lantern, which is the player.

### Death and reset
- **Defeat.** At zero health it is retired by iid (`WorldState.removed`: it does not return on a
  reload, a rest or quit and continue), sets `lamprey_defeated` to 1 and keeps the arena
  drained, and publishes `LampreyDefeated`. The scene gives hitstop, a flash and shake, and
  saves. The save format does not change: the flags are the save's own. The world validator knows
  both flags are set by the game (`Rules.code_flags`), so levels may read them.
- **The player dies.** The fight starts over: full health, phase 1, the tree reset, casings
  sealed, `lamprey_drained` cleared (the water comes back). Lamps keep what they were.
- **Fresh spawn.** A Lamprey that spawns (the room loads) clears `lamprey_drained` unless it
  is already defeated; health is not saved, so a reload starts the fight over.

### Rig
Drawn by `game/render/lamprey_view.py` from placeholder parts on an `engine.render.rig` rig:
head, jaw, lure (two bones, so it sways), fins; clips set the jaw and the lure per mode. The
body is a verlet `Chain` (`engine.render.verlet`) anchored behind the head, so the segments
follow it with inertia. Both are purely visual. The water is a dark overlay over everything
under the line; while drained it is gone.

### Feedback
`Bitten` (stone: shake, dust, hitstop), `Breached` (splash), `CasingBroken`, `Drained`,
`PhaseChanged`, `LampreyDefeated` are published on the bus; the scene turns them into shake,
particles, hitstop and sound. Hits on it flash it white and show damage numbers, as for any
enemy.

### Cistern_Lab
A 3x2 lab room at cell [70, 4]: black water over spikes, three platforms, four lamps, two with
a photocell directly above (so a lunge up at the lamp passes through its casing), a beacon, and
a wide door as the drained floor, powered by a FlagSwitch on `lamprey_drained`. `--room
Cistern_Lab`.

## Tuning parameters
`content/feel.toml`, `[lamprey]`.

| Name | Default | Notes |
|---|---|---|
| hp | 18 | six per phase |
| iframes | 0.35 | seconds between hits |
| contact_damage | 1 | |
| knockback | 160 | px/s |
| bait_flare, bait_lamp, bait_lantern | 1.0, 0.9, 0.5 | weights; braziers and beacons count as lamps |
| depth | 28 | px below the line when submerged |
| swim_speed | 130 | px/s |
| rise_time | 0.5 | seconds to surface |
| stalk_time | 1.0 | seconds hovering before a lunge |
| lunge_speed | 300 | px/s |
| lunge_range | 320 | px before it gives up |
| stun_time | 2.5 | seconds after biting stone |
| recover_time | 0.6 | seconds after a lunge into air |
| rest_time | 1.0 | seconds submerged between cycles |
| warn_time | 0.8 | phase 2 ripples before a breach |
| breach_time | 1.4 | seconds in the air |
| breach_span | 88 | px each side of the target |
| snuff_reach | 24 | px from a lamp at which a breach snuffs it |
| thrash_speed | 150 | px/s on the floor |
| thrash_time | 1.6 | seconds sliding at the player |
| gasp_time | 1.2 | seconds open |

## Acceptance criteria
- [x] The Lamprey gets health, a hurt box, a contact hit box and armor on its first tick, and
  the three phases follow its health.
- [x] It lunges at the brightest light (flare over lamp over lantern); a lunge into stone stuns
  it and opens its armor, a lunge into air does not.
- [x] Submerged it cannot be hit or hurt; breaching in phase 2 it takes a hit from above and
  none from the side, and snuffs the lamps it passes.
- [x] In phase 3 a lunge through a sealed photocell unseals it, lit photocells all at once drain
  the arena (`lamprey_drained`), and only then can it be hurt, in its gasps.
- [x] A phase change aborts the running step; the same sequence of light and position gives the
  same fight every time.
- [x] Killing it retires it, sets `lamprey_defeated`, and survives a reload and quit and
  continue; the arena stays drained.
- [x] The player dying resets the Lamprey, the casings and `lamprey_drained`.
- [x] `Cistern_Lab` holds the arena and can be reached with `--room Cistern_Lab`; it passes the
  world validator.
- [x] It draws as a rig with a verlet body, in every mode, without errors.

## Tests
`tests/unit/game/test_lamprey.py` drives `lamprey_system` on a small arena: bait choice, each
phase's cycle by ticks, armor and hurt box per mode, casings and the drain, reset and retiring.
`tests/integration/test_lamprey.py` loads `Cistern_Lab` and plays the fight with scripted
swings: phase transitions, damage windows, defeat across a reload and quit and continue, and
the player's death resetting it.
