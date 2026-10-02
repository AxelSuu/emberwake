# Lantern swing

**Milestone:** M9  **Status:** done  **Issue:** #114

## Goal
The player fights and touches the world with the lantern: a quick, readable swing that hits
enemies, bounces off them from above, and lights or breaks things. It should feel snappy (short
windup, hitstop on contact) and never cost movement control.

## Behavior

- **Action** `swing`, default keys C and J. Jump keeps Space and Z.
- **Direction** is chosen when the swing starts: Up held swings up; Down held in the air swings
  down; otherwise forward, the way the player faces.
- **Phases** in ticks: windup, active, recovery. The hitbox exists only while active. A press
  during the last `buffer` ticks of a swing (or any time it is idle) starts the next swing as
  soon as possible.
- A swing cannot start during a dash or while dead, and a dash cancels it.
- **Enemies** in the hitbox take `damage` once per swing, with knockback away from the player.
  A knocked-back enemy staggers: it slides, falls, cannot hurt by contact, and resumes its
  brain afterwards.
- **Pogo**: a down swing that hits an enemy, a hazard tile or a bouncy thing sets the player's
  vertical speed to `-pogo_speed`, ends a variable jump and refills the dash. Once per swing.
- **Recoil**: a forward swing that hits an enemy or a solid tile pushes the player back at
  `recoil` px/s. Once per swing.
- **Struck**: every entity with `Strikeable` in the hitbox gets one `Struck` event per swing,
  so lamps, braziers, breakables and bells react without the swing knowing them. A bouncy
  strikeable pogos like an enemy. For that tick its `Strikeable.struck` holds the direction, so
  systems after `strike_system` can react without subscribing.
- **Juice** (scene): `hitstop` ticks and `trauma` on an enemy hit, sparks, a white flash on the
  enemy, the lantern's light arcing with the swing, and a swish sound.

Frame data lives in `content/feel.toml` (`[swing]`) rather than in animation clips, so the
simulation stays tick-exact; the swing animation (#141) follows the phases.

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| windup | 2 | ticks before the hitbox appears |
| active | 5 | ticks the hitbox exists |
| recovery | 7 | ticks after, before the next swing |
| buffer | 6 | ticks a press is remembered |
| damage | 1 | |
| knockback | 160 | px/s given to enemies |
| reach | 22 | forward hitbox width, px |
| pogo_speed | 260 | px/s upward |
| recoil | 90 | px/s backward |
| hitstop | 2 | ticks, on an enemy hit |
| trauma | 0.12 | screen shake on an enemy hit |
| stagger | 0.25 | seconds an enemy is knocked about |

## Acceptance criteria
- [x] Swinging at a Clockrat twice kills it; it is knocked away and cannot hurt by contact while
  staggered.
- [x] A down swing onto an enemy or spikes bounces the player up and refills the dash.
- [x] A forward swing into a wall pushes the player back, and nothing breaks.
- [x] Each `Strikeable` in reach gets exactly one `Struck` per swing.
- [x] Up and down swings only reach above and below.
- [x] Old settings get the swing keys; C leaves jump only if jump still had the old defaults.
- [x] The Exterminator achievement can be earned by swinging.

## Tests
Unit tests drive `swing_system` and `strike_system` on a small world; an integration test swings
at the Clockrat in `Enemy_Yard`; the settings migration test covers v7 to v8.
