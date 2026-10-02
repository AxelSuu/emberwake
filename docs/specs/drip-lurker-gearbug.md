# Drip Lurker and Gearbug

**Milestone:** M9  **Status:** ready  **Issue:** #129

## Goal
Two Quarter enemies that make the player use light and the swing on purpose. The Drip Lurker
punishes walking through dark places and gives way to light; the Gearbug punishes swinging at its
front and rewards the pogo and the timing of its vent.

## Behavior

Both are `Brain` kinds in `game/enemies.py` (`drip_lurker`, `gearbug`) and follow the Clockrat
pattern: they get health, a hurt box and a contact hit box on their first tick, are staggered by
swing knockback and clear when dead.

### Armor
A new `Guard` component (`game/combat.py`) blocks hits without hurting or knocking the target.
A guard that is `active` blocks a hit when the attacker is on the side `facing` and not above the
target; `facing` 0 blocks from every side. A blocked hit publishes `Blocked`, is remembered per
hitbox activation (one `Blocked` per swing) and costs nothing. For a swing it counts like a wall:
a forward swing recoils the player, with sparks and a clang but no hitstop.

### Drip Lurker
Placed on the tile row under a ceiling; where it starts is its home.

- **ceiling**: hangs and waits. Hurts by contact. After `lurker_rest` seconds, when the player is
  below it within `lurker_reach` px sideways and `lurker_range` px down, with nothing solid or
  one-way in between, it goes to warn. A swing that hits it makes it drop at once.
- **warn**: trembles for `lurker_warn` seconds, then drops whether or not the player is still
  there (baiting works). Light cancels it: retract.
- **drop**: falls with gravity, hurting by contact, until it lands.
- **ground**: sits for `lurker_ground_time` seconds, hurting by contact and open to the swing,
  then climbs.
- **climb**: flies back to its home at `lurker_climb_speed` and is back on the ceiling; after
  `lurker_climb_max` seconds it is put home regardless.
- **retract**: while its spot is lit (`lurker_light` or more, not counting the player's own
  lantern, so a beacon, brazier or flare does it), it is tucked into the ceiling: harmless and
  fully armored (a swing clangs off it). It leaves retract once the light is under 60 % of
  `lurker_light`. On the ground, light sends it climbing.

### Gearbug
- **patrol**: walks, turns at walls and ledges. It ignores the player. After `gearbug_cycle`
  seconds it hisses.
- **hiss**: stops for `gearbug_hiss` seconds, rattling; still armored. A warning.
- **vent**: stops for `gearbug_vent` seconds with its front open and a puff of steam; then patrol.
- **Armor**: its front, the side it faces, is guarded in patrol and hiss. Swings from the front
  clang and recoil the player. Swings from behind, a down swing or a pogo from above, and any
  swing while it vents, hurt it. The pogo bounces the player as off any enemy. Touching it
  hurts the player as usual.
- It is drawn facing the way it walks, with a different image while venting.

## Tuning parameters
`content/feel.toml`, `[enemies]`.

| Name | Default | Notes |
|---|---|---|
| lurker_hp | 2 | |
| lurker_reach | 24 | px sideways from its centre that count as below it |
| lurker_range | 176 | px down that it looks |
| lurker_rest | 1.0 | seconds on the ceiling before it can warn again |
| lurker_warn | 0.5 | seconds of trembling before the drop |
| lurker_light | 0.2 | light level that makes it retract |
| lurker_ground_time | 1.5 | seconds on the ground |
| lurker_climb_speed | 70 | px/s |
| lurker_climb_max | 3.0 | seconds before it is put home |
| gearbug_hp | 3 | |
| gearbug_speed | 20 | px/s |
| gearbug_cycle | 4.0 | seconds of patrol between vents |
| gearbug_hiss | 0.6 | seconds of warning |
| gearbug_vent | 1.5 | seconds open |

## Acceptance criteria
- [ ] A Drip Lurker above a dark spot with the player below drops after the warn time, lands,
  stays `lurker_ground_time`, then climbs back and hangs again.
- [ ] It does not drop while its spot is lit by a beacon, brazier or flare, and retracts if lit
  during the warn or while on the ground; the player's lantern does not count.
- [ ] A retracted lurker neither hurts nor takes hits; a swing at it clangs.
- [ ] A swing that hits a hanging lurker makes it drop; it takes the hit.
- [ ] A forward swing at a Gearbug's front takes no health, does not stagger it and recoils the
  player; from behind it hurts.
- [ ] While it vents, a swing from the front hurts it; a down swing onto it always does and
  pogoes the player.
- [ ] The Gearbug walks, hisses, vents and walks again on its cycle, turning at walls and ledges.
- [ ] Both are in `Enemy_Gallery` (a lab room) and can be reached with `--room Enemy_Gallery`.

## Tests
Unit tests drive `enemy_system`, `combat_system` and `strike_system` on a small room (the
`Yard` and `Room` helpers): the Guard rule, every Lurker state change, the Gearbug cycle and
armor. An integration test loads `Enemy_Gallery`, lets a lurker drop on the player and swings at
a Gearbug from front and back.
