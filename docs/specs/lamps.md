# Lamps

**Milestone:** M9  **Status:** done  **Issue:** #121

## Goal
Lamp posts are the player's mark on the streets: swing at a dead one and it burns, and it
stays lit. Light-eaters undo that work unless a lit beacon holds the street, so beacons matter
beyond saving and the Belfry can threaten what the player lit.

## Behavior

- **Lamp**: a `Lamp` (`lit`, `protected`), a `Strikeable` and, while lit, a `LightSource`. An
  unlit lamp gives no light, so it neither lights its surroundings, refills flame nor draws
  enemies. Lit lamps light like braziers (`radius`, `color`) and refill flame like any light.
- **Lit by the swing**: a `Struck` on an unlit lamp lights it, from any direction, once per
  swing, and publishes `LampLit`. A lit lamp ignores the swing.
- **Protected by a beacon**: a lamp's level field `Beacon` is an entity ref to the beacon that
  holds it, in any room (empty: no beacon holds it). A lit lamp whose beacon is lit becomes
  `protected` and stays so, whichever of the two was lit first, and it can no longer be snuffed.
  The link is explicit so a street can be held by a beacon a room or two away, and so lamps
  in a room with a beacon are not protected by accident. Other things may protect a lamp later
  by setting `protected` (the Great Lamp, #138).
- **Snuffed**: `snuff` puts out a lit, unprotected lamp and publishes `LampSnuffed`; it does
  nothing otherwise. Anything that eats light calls it.
- **Wisp-eater**: with the player out of sight it picks the nearest lit, unprotected lamp
  within `wisp_attract` px and flies at `wisp_hunt_speed` to it (state `hunt`). Reaching
  `wisp_snuff_reach` px from the lamp it snuffs it and retreats. Seeing the player still sends
  it swooping; a lamp that is snuffed or protected meanwhile ends the hunt. Only lamps in
  loaded rooms can be snuffed.
- **Persisted** by iid like beacons (`Lamp`, not the link): a lit lamp is lit when its room
  reloads and after quitting and continuing, and a snuffed one stays dark. The save format
  does not change; the world state already holds persisted components.
- **Light %**: `lamp = "Lamp.lit"` in `[light]` of `content/areas.toml`, so lamps count with
  beacons ([areas](areas.md)). The area is recounted when a lamp is lit or snuffed, and the
  area banner shows again with the new percent (not in Trials).
- **Feedback**: lighting a lamp plays the kindle sound and throws a burst of sparks; snuffing
  one plays the fizzle sound.
- **Validator** (`just check`): a lamp's `Beacon` must point at a Beacon entity.

## Tuning parameters
`content/feel.toml`: `[lamps]` and `[enemies]`.

| Name | Default | Notes |
|---|---|---|
| radius | 80 | px a lit lamp lights (a brazier is 72, a beacon 96) |
| strength | 1.0 | |
| color | #fbb954 | |
| wisp_hunt_speed | 70 | px/s toward a lamp; hover is 40, a swoop 130 |
| wisp_snuff_reach | 10 | px from a lamp's centre at which it snuffs it |

## Acceptance criteria
- [x] Swinging at an unlit lamp lights it and it lights its surroundings; a lit lamp does
  nothing more.
- [x] A lit lamp is lit after its room unloads and reloads, and after quitting and continuing;
  a snuffed one stays dark.
- [x] A lit lamp under a lit beacon is protected, whichever was lit first, including a beacon in
  another room; one with no beacon, or an unlit one, is not.
- [x] A Wisp-eater flies to the nearest lit, unprotected lamp and snuffs it; a protected lamp is
  left alone; the player in sight still draws it off.
- [x] Lit lamps count in the area's light %, from the saved state when the room is not loaded,
  and the banner shows the new percent when one is lit or snuffed.
- [x] The validator rejects a lamp whose `Beacon` is not a beacon.
- [x] `Lamp_Lab` has lamps, a beacon and a Wisp-eater to try all of it with `--room`.

## Tests
`tests/unit/game/test_lamps.py` drives the lamp system and the Wisp-eater on a small world;
`tests/integration/test_lamps.py` plays `Lamp_Lab`, including reloads and a quit and continue;
`tests/unit/tools/test_level_validate.py` covers the `Beacon` check.
