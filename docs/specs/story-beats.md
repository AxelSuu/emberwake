# Story beats

**Milestone:** M9  **Status:** done  **Issue:** #138

## Goal
Three short, skippable scenes frame the slice: waking in the well, the Lamprey's reveal and the
Great Lamp lighting the Quarter, which ends on a credits stub.

## Behavior

- **Stage.** What a cutscene shows besides the world: a `fade` (0 clear, 1 black) drawn over the
  world and under the captions, a camera `focus` (a world point the camera eases to instead of
  the player, with its usual smoothing) and a `caption` (a string key shown in the lower third).
  Input is locked and the HUD hidden while a cutscene runs (#cutscene engine); the world keeps
  running.
- **Scripts** live in `game/story.py`, by name. Each one is skippable with Enter: skipping runs it
  to its end state at once, so flags are set and lamps lit as if it had played. Every script
  ends with the stage cleared and sets `story_<name>` to 1.
- **intro**: on a new game started from the menu (not a continue, `--room`, replay or Trial). The
  screen starts black, the camera on Wake's beacon; it fades in over 1.5 s, shows
  `story.intro.1` then `story.intro.2` for 2.5 s each, and the camera eases back to the player.
- **StoryBeat** (`Script`): an invisible zone. When the player first enters it, its script plays,
  unless `story_<Script>` is already set. `Requires` and `Unless` gate it like any entity.
- **lamprey_reveal**: a StoryBeat over the Cistern's entrance, `Unless = "lamprey_defeated"`.
  The camera eases to the Lamprey, `story.lamprey.1` and `story.lamprey.2` show for 2 s each,
  and it eases back.
- **GreatLamp**: the Great Lamp in Market Square. It stands cold from the start, can be kindled
  (interact) only while `lamprey_defeated` is set and `great_lamp` is not, and burns (its lit
  sprite and a big light) once `great_lamp` is set. Kindling it plays **great_lamp**: focus on
  the lamp, a flash, then every Lamp in the area lights in turn, nearest first, `lamp_step`
  apart (loaded ones in the world, the others in the saved state), the area recounts its light
  (so the grade warms), and
  `great_lamp`, `hesper_stage` 1 and `quill_stage` 2 are set, so Hesper stands by the lamp,
  Quill waits at the road to Brass Gardens and the Tinker moves to a stall in the Square.
  `story.great_lamp.1` and `.2` show, then the **credits** stub opens over the game.
- **Credits.** A list of `credits.*` lines; any key or Back returns to the game.
- **Validator.** The flags the story sets count as written (`Rules.code_flags`).

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| fade in | 1.5 s | intro |
| caption | 2.5 s, 2 s | intro, reveal; the Great Lamp's are 2.5 s |
| lamp_step | 0.15 s | between lamps lighting |

## Acceptance criteria
- [x] A new game from the menu opens on the intro; continuing, `--room` and Trials do not.
- [x] Each script, played or skipped, ends with its flags set and the stage cleared.
- [x] The reveal plays once, on entering the Cistern, and never after the Lamprey is dead.
- [x] Kindling the Great Lamp lights every Lamp of the Quarter, loaded or not, sets the stage
  flags, moves the NPCs and opens the credits; Back returns to the game.
- [x] The Great Lamp can only be kindled once the Lamprey is dead, and burns after.

## Tests
`tests/unit/game/test_story.py` (scripts against a fake director), `tests/integration/test_story.py`
(the intro from the menu, the reveal zone, the Great Lamp and credits).
