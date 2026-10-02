# Lifts and moving platforms

**Milestone:** M9  **Status:** done  **Issue:** #125

## Goal
Rooms that move: a platform the player rides up a shaft or across a pit, driven by a lever, a
plate or a flag, or carrying on by itself. It never crushes the player and never drops them.

## Behavior

- **One entity, two uses.** `Platform` (prefab `platform`) is a box, 48x16 by default and
  resizable, on a path. A lift is a platform wired to a switch; a moving platform is one with no
  wiring. Both are the same code.
- **Path.** Its home is where the level places its top-left corner. `Path` is an array of
  `PathNode` refs, in the same room: each marks the top-left corner the platform visits next, in
  order. A platform with no `Path` stays put (and fails the world validator). Nodes are plain
  markers, never drawn and never solid. `Speed` (px/s) overrides the default; 0 uses it.
- **Wired: a lift.** The platform has a `Receiver` like a door (`Mode`, `Invert`). While powered it
  travels along the path to the last node and stays there; while unpowered it travels back to its
  home and stays there. It is the same distance either way, so a lift left at the top by a
  lever comes down when the lever is thrown back. A lift stopped half way, because the power
  changed or something held it, resumes toward whichever end it is now sent to.
- **Unwired: a loop.** With no switch targeting it, the platform goes back and forth along the
  path, resting `dwell` seconds at each end.
- **Solid from every side.** Like a crate, a platform is a solid box for the player (floor, walls,
  ceiling; it can be stood on, jumped from and wall-jumped off) and for crates, which rest on it.
  It is fully solid, not one-way: a lift is also a moving wall, the sub-stepped collision is the
  engine's box mover (`move` with `solids`), the same on every platform, and there is no
  special "inside the platform" case to resolve. Enemies ignore platforms, as they ignore crates.
  Level designers who want to be jumped through from below leave room beside the platform.
- **Carries what stands on it.** A rider is the player, or a push crate, resting on the platform's
  top (feet within 0.5 px of it and overlapping its width), and anything resting on a rider in
  turn. Each tick, before the player's own move, every rider is moved by the platform's
  displacement through the ordinary collision (so a rider stops at walls), then the platform
  takes the step. A rider keeps no momentum: stepping off a moving platform is a standing start.
- **Never crushes, never tunnels.** The platform takes a step only if the whole step is free:
  every rider could be carried by it, and its new position overlaps no solid tile, no other
  platform and no body that is not a rider (the player under a descending platform, beside a
  sweeping one, or a crate in its way). Otherwise it holds still for that tick, and tries again
  the next. A step is at most `speed * dt` (under a pixel), so nothing is skipped over. A player
  pinned against a wall by a platform is held, not hurt, and steps away when they like.
- **Persistence.** How far along the path a platform is, its direction and its rest are saved by
  iid (`PlatformRest`), like any entity state (ADR 0015): it is where it was left when its room
  reloads and on save and continue, applied on the first frame. A lift whose power is a flag
  (a `FlagSwitch`) is therefore at the top for good once raised and the flag holds, and starts
  from the bottom otherwise. A platform in an unloaded room does not move.
- **No soft-lock.** A platform never traps anyone (it holds rather than crushes), and a lift
  needed to progress is powered by something the player can always reach: a lever beside it, or
  a `FlagSwitch`, as for the Cistern lift up to the Square, which runs once `lamprey_defeated`
  holds. Resting at a beacon does not move platforms.
- **Art.** A placeholder: a plank slab with a metal underside (`platform`), distinct from the
  crumbling platform.
- **World validator.** A platform is a way across for the reachability search: the cells it
  sweeps count as one-way floor, when it is unwired (it loops), or when a source wired to it is
  available, as for a door. A bad `Path` (missing ref, not a `PathNode`, other room, empty)
  is reported.

## Tuning parameters
`content/feel.toml`, `[platforms]`.

| Name | Default | Notes |
|---|---|---|
| speed | 48 | px/s along the path |
| dwell | 0.8 | s a looping platform rests at each end |

## Acceptance criteria
- [x] A powered lift travels to its last node at `speed` and stays; unpowered it returns.
- [x] An unwired platform loops along its path and rests `dwell` at each end.
- [x] A player or crate standing on a moving platform is carried by its displacement, up, down
  and sideways, and a crate stacked on a carried crate too; a rider that is jumping away is not.
- [x] The player can stand on, jump from and wall-slide against a platform.
- [x] A platform does not move into a player below, beside or above it, nor into a rider that
  would be pressed into a wall or ceiling, and moves on once the way is clear. Nobody is hurt.
- [x] A platform's place on its path survives its room reloading, and quitting and continuing.
- [x] Two runs of the same input leave platforms and riders in the same places.
- [x] A gap crossable only by a lift whose lever is reachable, or by a looping platform, passes
  the world validator; a lift whose lever is not reachable is reported.
- [x] `Lift_Lab` has a lever lift, a looping platform over spikes and a two-node lift.

## Tests
`tests/unit/game/test_platforms.py` drives the system on a small world: carrying, wiring,
looping, holding, persistence; `tests/integration/test_lifts.py` plays `Lift_Lab`;
`tests/unit/tools/test_world_validate.py` (`TestLifts`) covers the validator rule.
