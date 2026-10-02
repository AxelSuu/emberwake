# Encounters

**Milestone:** M9  **Status:** draft  **Issue:** #126

## Goal
A fight with a beginning and an end: stepping into an arena shuts its doors, waves of enemies
come out of the markers, and the last one's death opens the way and powers whatever the arena
guards. A cleared arena stays cleared.

## Behavior

### Placed in the level
- **Encounter**: a resizable zone. Fields `Doors` (Doors it shuts while it runs) and `Targets`
  (receivers it powers once cleared). It carries a `Switch` that is on once cleared.
- **WaveSpawn**: a marker, one tile. Fields `Encounter` (a ref to its Encounter, in the same
  room), `Wave` (1 and up) and `Kind` (an enemy prefab: `clockrat`, `gloomcrawler`, `wisp_eater`,
  `drip_lurker`, `gearbug`, `clockrat_king`). The enemy appears standing on the marker.
- Waves are numbered from 1 without gaps; every Encounter has at least one WaveSpawn in wave 1.

### States
- **idle**: nothing happens until the player's centre is inside the zone.
- **active**: the Encounter shuts its Doors (a Door closes once the player is out of the
  doorway), publishes `EncounterStarted` and spawns wave 1. When every enemy of the current wave
  is gone it waits `wave_delay` seconds and spawns the next wave. When the last wave is gone it
  is cleared.
- **cleared**: Doors open, the Encounter's `Switch` turns on (so its Targets are powered, also
  while its room is unloaded) and `EncounterCleared` is published. It never starts again. The
  cleared flag is the `Switch` state, saved by iid like a lever's; the save format does not
  change.

A Door named in `Doors` is open except while its Encounter is active; its `Mode` and `Invert`
are ignored.

### Reset
An active Encounter that loses its fight resets: the wave enemies despawn, the doors open and
it is idle again, with nothing kept. It resets when the player dies, when the player has been
outside the zone for `leave_grace` seconds, and when its room unloads. Dying at a beacon or at
a hazard both count: see `death-and-recovery.md`.

### Wave enemies
A wave enemy is an ordinary enemy from its prefab with a `Minion` owned by the Encounter, the
same ownership the Clockrat King's rats use, so it goes when the Encounter does. It is not a
placed enemy: it is never saved, and a `clockrat_king` that is a wave enemy is not retired by
iid when killed (a cleared Encounter does not need it to be). Its iid for seeding is
`<WaveSpawn iid>:wave`, so a replay spawns and summons the same way. A King as wave enemy calls
rats to the `RatSpawn` markers of its room as usual; those rats do not count for the wave and go
when the King does.

### Feedback
Starting and clearing shake the screen (`trauma`); each spawn publishes `Summoned`, drawn as the
puff at the marker. There is no art of its own: markers and zones are not drawn.

## Tuning parameters
`content/feel.toml`, `[encounters]`.

| Name | Default | Notes |
|---|---|---|
| wave_delay | 1.0 | seconds between a wave's last death and the next wave |
| leave_grace | 1.5 | seconds outside the zone before an active Encounter resets |
| trauma | 0.2 | screen shake on start and on clear |

## Acceptance criteria
- [ ] Entering the zone starts the Encounter: Doors close, wave 1 spawns at its markers.
- [ ] A wave's enemies are of the `Kind` of their marker; the next wave comes `wave_delay`
  after the last of the previous one dies, and not before.
- [ ] Killing the last wave clears it: Doors open and its Targets are powered.
- [ ] A cleared Encounter stays cleared after a room reload, resting, and quit and continue,
  and keeps powering its Targets while its room is unloaded.
- [ ] Dying mid-fight, leaving the zone for `leave_grace` seconds or unloading the room resets
  it: wave enemies are gone, Doors open, nothing is saved, and it can start again.
- [ ] A Clockrat King works as a wave enemy and its rats go with it.
- [ ] Wave enemies are not saved, and a wave King is not retired when killed.
- [ ] The world validator rejects a WaveSpawn without a valid Encounter or Kind, gaps in the wave
  numbers, an Encounter without a first wave, and Doors or Targets that do not exist; the
  walker treats a locked Door as passable.
- [ ] `Arena_Lab` (a lab room) holds an Encounter of two waves, a Door and a reward, and can be
  reached with `--room Arena_Lab`.

## Tests
`tests/unit/game/test_encounters.py` drives `encounter_system` on a small world: the lock,
waves, clear, reset on death and on leaving, persistence of the cleared state and the King as a
wave enemy. `tests/unit/tools/` covers the validator. `tests/integration/test_encounters.py`
loads `Arena_Lab` and plays it through, including quit and continue.
