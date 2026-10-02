# World flags

**Milestone:** M9  **Status:** done  **Issue:** #119

## Goal
The world changes with the story without one-off code: NPCs move, doors open and things appear
or vanish after events, all decided by conditions in the level data.

## Behavior

- **Facts.** Conditions read the save slot's flags (integers, a missing flag is 0) and, under
  `has.`, what the player owns: `has.<ability>` is 1 once the ability is owned, `has.<item>` is
  the item's count (`has.flare`, `has.shard>=3`). One namespace for both, since names in
  `content/grants.toml` are unique.
- **Syntax** is the dialogue's: a name (non-zero), `!name`, or a name compared (`>=`, `<=`, `>`,
  `<`, `==`, `!=`) with an integer. One condition per field; `Requires` and `Unless` together
  cover a range (`Requires = "stage>=2"`, `Unless = "stage>=3"`).
- **Requires and Unless.** Every LDtk entity type has both, empty by default. An entity belongs in
  the world while its `Requires` holds (or is empty) and its `Unless` does not (or is empty).
  - When a room loads, entities that do not belong are held back.
  - When the facts change (a dialogue, a SetFlag, a grant, the shop, the F7 overlay), loaded
    rooms are checked again in the same tick: live entities that no longer belong despawn,
    saving their persisted components as a room unload does, and held-back entities that now
    belong spawn with their saved state.
  - Held back is not killed or collected: a killed enemy does not return because a flag changed
    (a rest does that), and a collected pickup never returns.
  - A PlayerStart ignores them: respawn points are read straight from the level.
  - A door that despawns leaves its cells as they were. To open a door on a flag, wire a
    FlagSwitch to it instead of gating the door.
- **FlagSwitch** (`Condition`, `Targets`): a switch that is on while its condition holds. Not
  drawn and not usable. It powers receivers like a lever does, also while its room is unloaded:
  signals evaluate its condition instead of reading saved state.
- **SetFlag** (`Flag`, `Value` 1, `Mode` set or add): an invisible zone. When the player steps
  in, it sets the flag to `Value`, or adds `Value` to it. Stepping in again does it again (which
  matters for add); an `Unless` on its own flag makes it fire once.
- **Beacon** `Flag`: relighting the beacon sets the flag to 1, so a FlagSwitch can open a door
  once a beacon somewhere is lit (the Cistern Gate waits on both Quarter Lamps).
- **Dev.** F7 lists the flags the levels read or write next to the dialogue's; toggling one
  changes the world as soon as the overlay closes. `--flags` seeds flags before the first room
  spawns.
- **Validation.** `tools.levels validate` reports a `Requires`, `Unless` or `Condition` that does
  not parse.

## Tuning parameters
None.

## Acceptance criteria
- [x] An entity whose `Requires` fails or whose `Unless` holds is not spawned with its room.
- [x] A flag change spawns entities that now belong and despawns ones that do not, live, in
  loaded rooms; a despawned entity's persisted state comes back with it.
- [x] A killed enemy stays dead and a collected pickup stays gone when flags change.
- [x] `has.<ability>` and `has.<item>` read the player's abilities and item counts.
- [x] A FlagSwitch powers its targets while its condition holds, also from an unloaded room.
- [x] Touching a SetFlag sets its flag, or adds to it.
- [x] Toggling a flag with F7, a `--flags` seed, a dialogue and a grant each make gated
  entities react.
- [x] The validator reports a malformed condition.
- [x] Lighting a beacon with a `Flag` sets it; the validator counts it as written and set once
  the beacon is reached.
- [x] Enemy_Yard uses each piece: meeting the Tinker opens the alcove door (FlagSwitch), his
  flares bring out an ember (`has.`), and stepping into the alcove (SetFlag) takes that ember
  away (`Unless`) and lights a brazier (`Requires`).

## Tests
`tests/unit/engine/test_spawning.py` (the gate), `tests/unit/game/test_flags.py` (facts,
FlagSwitch, SetFlag, wiring from unloaded rooms), `tests/unit/tools/test_level_validate.py`,
`tests/integration/test_flags.py` (Enemy_Yard, F7, `--flags`, dialogue).
