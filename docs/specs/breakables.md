# Breakables

**Milestone:** M9  **Status:** ready  **Issue:** #123

## Goal
The lantern changes the world: cracked walls open shortcuts and secrets, crates and pots pay out
embers, and crumbling platforms make the player keep moving. What breaks stays broken.

## Behavior

- **Struck** (from the [lantern swing](lantern-swing.md)) is all that breaks things. One strike
  is enough, from any direction: forward into a wall, up into a ceiling, down into a floor (no
  pogo; the player drops through).
- **Cracked walls** own the cells under them like doors: solid until struck, then empty. A
  forward swing recoils off them as off any wall.
- **Crates** are solid too, so they can be stood on; **pots** are not. Both drop embers.
- **Broken for good**: a broken wall, crate or pot is retired by iid (`WorldState.removed`), so it
  never spawns again: not when its room reloads, not after quitting and continuing. The save
  format does not change.
- **Embers** fly out as loose embers, as many as the thing's `Embers` field. Their scatter comes
  from a `random.Random` seeded with the thing's iid, so the same crate always breaks the same
  way. They fall and bounce, then after `ember_settle` home in on the player through anything
  and count as collected (`Collected`) on touch, like placed embers.
- **Crumbling platforms** are one-way cells. The player standing on one starts it shaking; it
  clears `crumble_delay` after the landing and comes back `crumble_return` later, but not while
  the player overlaps its cells. Only the player sets one off. Its state is not saved: a room
  that reloads has its platforms whole.
- **Feedback**: breaking throws debris, plays a break sound, stops time for `hitstop` ticks and
  shakes the screen by `trauma`. A crumbling platform trembles while it shakes, throws debris
  and creaks when it goes, and leaves a faint outline while gone.
- Room art is painted from the level's own tiles, so cells that entities change (doors, walls,
  platforms) are drawn by those entities and never linger in the baked art.

## Tuning parameters
`content/feel.toml`, `[breakables]`.

| Name | Default | Notes |
|---|---|---|
| crumble_delay | 0.5 | seconds from landing until a crumbling platform clears |
| crumble_return | 2.0 | seconds it stays gone, at least |
| ember_speed | [60, 140] | px/s range a loose ember is flung at, upward |
| ember_gravity | 600 | px/s² |
| ember_settle | 0.4 | seconds before loose embers home in on the player |
| ember_pull | 240 | px/s while homing |
| hitstop | 3 | ticks, on breaking something |
| trauma | 0.15 | screen shake on breaking something |

## Acceptance criteria
- [ ] A cracked wall blocks the player until struck; one swing, in any direction, empties its
  cells.
- [ ] A broken wall, crate or pot stays broken when its room reloads and after quitting and
  continuing.
- [ ] Breaking a crate or pot flings its embers, which reach the player and count as collected;
  the same crate always flings them the same way.
- [ ] A crumbling platform holds the player, clears 0.5 s after they land and is back 2 s later.
- [ ] A crumbling platform does not come back while the player overlaps it.
- [ ] Breaking stops time briefly and throws debris; a crumbling platform trembles before it
  goes.

## Tests
`tests/unit/game/test_breakables.py` drives the systems on a small world;
`tests/integration/test_breakables.py` plays them in `Break_Lab`, including reloads and a
quit and continue.
