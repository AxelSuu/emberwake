# Areas

**Milestone:** M9  **Status:** done  **Issue:** #120

## Goal
Rooms belong to areas. Crossing into another area announces it, and an area gets its colour
back as the player lights it, so progress shows on screen and not only in menus.

## Behavior

- **Area**: the level field `Area` (default `quarter`) names a key of `content/areas.toml`. Its
  player-facing name is the string `area.<id>.name`. The dev rooms are in `lab`.
- **Music**: the level field `Music` names a stem set; empty means the area's `music`. Nothing
  plays yet: the scene exposes the active room's set for the music system of M10.
- **Banner**: entering a room whose area differs from the one shown last puts that area's name
  in the HUD banner, with its light % under it. Starting a session counts as entering (new
  game, continue, `--room`, a respawn in another area); Trials show no banner.
- **Light %** of an area = what is lit / what there is to light, over every room of the area,
  loaded or not. What counts is data: `[light]` in `content/areas.toml` maps a prefab to the
  `Component.field` that is true once it is lit; the prefab must persist that component. The
  value comes from the saved world state, or from the level file while the entity was never
  saved. Today beacons (`Beacon.lit`) and lamps (`Lamp.lit`) count; Lost Lights and Echoes
  (#127) each add a line.
- The percent is rounded down, so 100 % means everything. An area with nothing to light counts
  as fully lit and shows no percent.
- It is recounted when the player enters another area, when a beacon is lit and when the pause
  menu opens. Whatever else lights up recounts on its own event.
- **Saturation**: the grade's saturation is multiplied by `dim + (1 - dim) * light`, easing at
  `rate` per second (a session starts at its value). A dark area looks washed out, a fully lit
  one keeps its preset's colour. It is part of colour grading, so the grading setting turns it
  off too.
- **Pause menu**: the area's name and light % sit under the title.
- **Validator** (`just check`): `Area` must be a known area and have a name; `Music` and each
  area's `music` must be lowercase names (`[a-z][a-z0-9_]*`); each light rule must name a prefab
  that persists the component, and the field must exist.

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| dim | 0.7 | share of the preset's saturation kept at 0 % light (`content/areas.toml`) |
| rate | 0.5 | light per second the saturation eases by |

## Acceptance criteria
- [x] A room without `Area` is in `quarter`; an empty `Music` falls back to the area's set.
- [x] Crossing into another area shows its banner; moving within an area does not.
- [x] A session starts with its area's banner; a Trial shows none.
- [x] Light % counts lit beacons over all beacons of the area, unloaded rooms included, from the
  saved world state.
- [x] A prefab added to `[light]` counts with no code change.
- [x] An area with nothing to light is 100 % and shows no percent.
- [x] At 0 % light the saturation is `dim` of the preset's; at 100 % it is the preset's.
- [x] The validator rejects unknown areas, bad music names and light rules that cannot be saved.

## Tests
`tests/unit/game/test_areas.py`, `tests/integration/test_areas.py`,
`tests/unit/tools/test_level_validate.py`, `tests/unit/game/test_hud.py`.
