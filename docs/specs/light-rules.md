# Light rules

**Milestone:** M9  **Status:** done  **Issue:** #116 (replaces the M5 rules of #40)

## Goal
Darkness presses on the player without being a second death bar: running out of light makes
things worse, slowly, and light is always the way back. Flares are precious, and flame is worth
saving because it heals.

## Behavior

- **Flame** (the `Ember` component; "embers" are the currency) drains at `drain` per second
  away from light other than the player's own lantern, and refills at `refill` per second in it.
- **Gutter**: at zero flame the lantern's reach (for lightforms, enemies and the light pool)
  drops to `gutter_radius` of normal, and every `gutter_every` seconds the player loses 1
  health, invulnerability frames permitting. Any light ends it.
- **Flares** are carried as charges (`flare_charges` to start; pouches add more later). A throw
  spends one; with none left, the throw fizzles. Standing in light wins one back every
  `flare_refill` seconds, and resting at a beacon fills them all.
- **Kindle**: holding Down for `kindle_ticks`, grounded, still, and pressing nothing else, while
  hurt and holding at least `kindle_cost` flame, turns that flame into 1 health. Letting go or
  moving starts over. The lantern swells while it charges.
- **Beacons** are rests: relighting (or using a lit one again) refills health, dash, flame and
  flares, and saves.

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| drain | 2.0 | flame per second in the dark |
| refill | 25.0 | flame per second in light |
| gutter_radius | 0.33 | share of the lantern's reach while guttering |
| gutter_every | 4.0 | seconds per 1 damage while guttering |
| flare_charges | 2 | |
| flare_refill | 2.0 | seconds in light per flare |
| kindle_ticks | 48 | ticks Down is held |
| kindle_cost | 30.0 | flame per 1 health |

## Acceptance criteria
- [x] At zero flame the player is not killed; health drops by 1 every `gutter_every` seconds.
- [x] The lantern's reach shrinks while guttering, and light ends the gutter.
- [x] A third flare with two charges fizzles; light brings charges back; beacons fill them.
- [x] Holding Down still for `kindle_ticks` heals 1 for `kindle_cost` flame; moving resets it;
  nothing happens at full health, in the air or without the flame.
- [x] A beacon heals fully.

## Tests
`tests/unit/game/test_light.py`, `test_kindle.py`, `test_beacons.py`;
`tests/integration/test_light_rules.py` and `test_flares.py` in real rooms.
