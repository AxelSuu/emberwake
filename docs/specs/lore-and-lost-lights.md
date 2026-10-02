# Signposts, Echoes, Lost Lights and Trial doors

**Milestone:** M9  **Status:** draft  **Issue:** #127

## Goal
The world talks to the player and has things to find: signs that teach the controls with the
player's own keys, ghosts that replay a lamplighter's last moments, small spirits to lead to a
beacon, and doors into the Trials.

## Behavior

- **Signpost** (`Text`): while the player is within `reach` px of it, the string `sign.<Text>` is
  shown above it. `{left}`, `{jump}` and the other action names in the string become the first
  key bound to that action, as `[Space]`, and follow rebinding at once. No input is needed.
- **Echo** (`Id`): Interact ("listen") plays `content/echoes/<Id>.json`, a replay in the format
  of the Trials ghosts, as a translucent ghost that starts at the Echo's feet and runs the
  player's movement code, so it follows the recorded path in a room with the same layout. The
  string `echo.<Id>` is shown above the Echo while it plays and for `hold` seconds after. Using
  it again replays it. The first time sets `Echo.seen` (saved by iid), the flag `echo_<Id>` to 1
  and adds 1 to the count flag `echoes`, which the journal (M11) reads.
- **Lost Light** (`Id`): a spirit that waits where it was placed. When the player comes within
  `notice` px it follows: it moves to where the player was `delay` seconds ago (a trail of past
  positions), through rooms as the player crosses them. When it comes within `rescue` px of any
  Beacon it is rescued: `LostLight.rescued` is saved by iid, the flag `lost_light_<Id>` is set
  to 1, the count flag `lost_lights` goes up by 1, and it stops being drawn or lit. Hesper (#131)
  reads `lost_lights`; the Market Square places a spirit with `Requires = "lost_light_<Id>"`. When
  the player dies, a following light returns to where it was placed and waits again.
- **Trial door** (`Trial`, a key of `content/trials.toml`): Interact ("enter") unlocks that Trial
  in the Trials menu (kept in `records.json`, so for every slot) and starts it. A Trial with
  `locked = true` is listed in the menu only once a door has unlocked it; others are always
  listed. A Trial started from a door ends at the title screen, as one from the menu does.
- **Light %**: `[light]` in `content/areas.toml` counts `lost_light = "LostLight.rescued"` and
  `echo = "Echo.seen"`.
- **Validator**: the world test checks that every Echo has a replay and a string, every Signpost
  a string and every Trial door a Trial.

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| Signpost `reach` | 28 px | how near the player must be to read |
| Echo `hold` | 3 s | text stays this long after the ghost stops |
| Lost Light `delay` | 0.5 s | how far behind the player it floats |
| Lost Light `notice` | 32 px | distance at which it starts following |
| Lost Light `rescue` | 24 px | distance from a beacon at which it is rescued |

## Acceptance criteria
- [ ] A signpost shows its text only while the player is near, with the current keys; rebinding
  an action changes the key shown.
- [ ] Using an Echo plays its replay as a translucent ghost and shows its line; a missing replay
  still shows the line.
- [ ] A heard Echo is saved: `echo_<Id>` is set, `echoes` counts it once however often it is
  heard, and it counts toward the area's light %.
- [ ] A Lost Light follows the player about `delay` seconds behind, also across rooms.
- [ ] Leading it to a beacon rescues it once: flag, count, light %, saved and gone from the room.
- [ ] Dying sends a following light home; it can be led again.
- [ ] A Trial door unlocks its Trial in the menu and starts it; a locked Trial is hidden until
  then.
- [ ] `Lore_Hall` (a lab room) has each of them.

## Tests
`tests/unit/game/test_lore.py` (signposts, Echoes, Trial menu), `tests/unit/game/test_lost_lights.py`,
`tests/integration/test_lore.py` (`Lore_Hall`, saving, rebinding).
