# Death and recovery

**Milestone:** M9  **Status:** done  **Issue:** #117

## Goal
Platforming mistakes are cheap and fast to retry; losing a fight costs something you can win
back. The player always knows where they will be after dying.

## Behavior

- **Hazards** (spikes, the void): the player loses 1 health and comes back at the entrance of
  the room they came in by, keeping the health and flame they had. If that was the last pip, it
  is a death instead.
- **Death** (health runs out): after the usual hitstop and delay the player comes back at the
  last relit beacon (or the start of the game) with full health, flame and flares. Regular
  enemies in the rooms around come back too.
- **Cinder**: on death, the embers carried drop as a Cinder where the player last stood on
  solid ground (never over spikes or the void). Touching it gives them back. Dying again before
  that loses the old Cinder's embers for good. The Cinder is saved with the slot, so quitting
  does not dodge it.
- **Trials** are unchanged: any death restarts the attempt at the start, whole, with no Cinder.
- Killed enemies come back whenever their room spawns again (a bug kept them dead before).

## Acceptance criteria
- [x] Spikes cost 1 health, keep the rest, and send the player to the room's entrance.
- [x] Dying restores full health at the beacon (or start) and drops the carried embers.
- [x] Touching the Cinder gives the embers back; dying again loses them.
- [x] Old saves (v1) load without a Cinder.
- [x] Killed enemies come back after a death or a rest.

## Tests
`tests/integration/test_death.py`, `tests/unit/game/test_save.py`, `tests/unit/engine/test_ecs.py`.
