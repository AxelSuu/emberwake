# Push crates

**Milestone:** M9  **Status:** done  **Issue:** #124

## Goal
Weight the world: the player shoves a crate along the floor, drops it off a ledge, stacks it and
stands on it, and a crate on a pressure plate holds the plate down so the player can walk away.

## Behavior

- **Not the breakable `crate`.** `PushCrate` (prefab `push_crate`) is a different thing from the
  [breakable](breakables.md) `Crate`: it cannot be struck, never breaks and drops nothing. The
  swing passes through it.
- **A box, not a tumbling prop.** A crate is a 16x16 axis-aligned box with gravity. It never
  rotates, so standing on it and stacking it are exact. Its simulation is the engine's
  deterministic box mover (`move` with `solids`), the same code on every platform, so a replay
  plays the same everywhere. It does not use pymunk: pymunk is optional, whether it runs in the
  browser is still open (#2), and a second backend with its own results would break replays
  across builds. Flares and other loose props stay on `PropWorld` (ADR 0007).
- **Solid for the player.** The player's collision treats every crate as a solid box: walls on
  its sides, a ceiling underneath, a floor on top (a crate can be stood on and jumped from,
  and wall slides and wall jumps work off its sides). Enemies ignore crates.
- **Pushed by walking.** While the player is grounded, not dashing, holding a direction and
  flush against a crate's side in that direction, the crate moves that way at `push_speed`, and
  the player moves with it at the same speed. A crate against a wall, a closed door or another
  crate that cannot move does not move, and stops the player like a wall. Only the player moves
  a crate sideways; there is no pulling, and a crate has no friction: a crate pushed out from
  under another leaves it behind, and the one above falls.
- **Falls and stacks.** Gravity pulls crates down to `max_fall`. They land on solid tiles,
  one-way platforms, the player's head and each other, and rest there. A crate is never inside
  a solid tile. Crates are stepped bottom first, so a stack stays whole.
- **Weighs plates.** A `PressurePlate` is down while the player stands in it or a crate has at
  least `share` (0.5) of its width over the plate, resting in its rows. A crate on a plate keeps
  its `Switch` on, so a door stays open without the player.
- **Void.** A crate that falls out of the world is back at its home (where the level places it).
- **Persistence.** Where a crate is, as an offset from its home, is saved by iid (`CrateRest`),
  like any entity state (ADR 0015): it is where it was left when its room reloads, and a save
  (a beacon, or quitting) keeps it. It is restored on spawn, so the first frame already shows it
  in place. A crate in an unloaded room does not exist: it weighs nothing there.
- **Rest.** Resting at a beacon sends every crate home, in loaded and unloaded rooms alike, as
  enemies come back. This frees a crate pushed into a corner or a pit with no way out, so no
  crate can soften-lock a room. Doors held open by a crate close again, since the plate is up.
- **Art.** A placeholder: a darker, banded crate (`push_crate`) that cannot be mistaken for the
  breakable one.
- **World validator.** A door powered by a PressurePlate counts as openable when the plate is
  reachable, or the search reaches a PushCrate in the plate's room. It does not check that the
  crate can really be pushed there.

## Tuning parameters
`content/feel.toml`, `[crates]`. The share of a crate over a plate that presses it is `Weight.share`
(0.5) in the `push_crate` prefab.

| Name | Default | Notes |
|---|---|---|
| push_speed | 60 | px/s a pushed crate and the player move at |
| gravity | 1200 | px/s² |
| max_fall | 360 | px/s |

## Acceptance criteria
- [x] The player cannot walk through a crate, stands on it and can jump from its top.
- [x] Walking into a crate pushes it at `push_speed` and the player keeps pace; a crate against
  a wall or another stuck crate stops the player.
- [x] A crate pushed off a ledge falls and lands on the floor, a one-way platform or another
  crate, and a stack of two stays whole.
- [x] A crate on a PressurePlate holds it down with the player away, and releases it when
  pushed off; a crate barely on the plate does not press it.
- [x] A crate's position survives its room unloading and reloading, and quitting and continuing.
- [x] Resting at a beacon sends crates home, in unloaded rooms too; a crate that falls out of the
  world is home again.
- [x] A door whose only plate is out of the player's reach but shares a room with a reachable
  PushCrate passes the world validator; without the crate, or with the crate in another room,
  it is reported.
- [x] Two runs of the same input leave crates in the same places.

## Tests
`tests/unit/engine/test_physics.py` covers `move` and `overlaps` against solids;
`tests/unit/game/test_crates.py` drives the systems on a small world;
`tests/integration/test_crates.py` plays `Crate_Lab`: pushing a crate onto its plate, dropping
one from a ledge, reloads, resting and a quit and continue;
`tests/unit/tools/test_world_validate.py` covers the validator rule.
