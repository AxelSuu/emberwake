# Light switches

**Milestone:** M9  **Status:** done  **Issue:** #122

## Goal
Light and the lantern become signals. A photocell opens a door while something bright is near
it, a brazier the player lights keeps a door open for good, and a bell rings a short signal and
stuns whatever is nearby.

## Behavior

All three are switches: their `Targets` (entity refs) are receivers, and doors read them through
the [signal system](../../src/emberwake/game/signals.py) like levers and plates.

- **Photocell** (`Targets`, `Threshold`): on while the light at its centre, from any source
  including the player's lantern, is at least `Threshold` and above zero. Off again when the
  light goes (a flare burns out, the player walks off). Not saved: an unloaded photocell is off.
- **Brazier** (`Targets`, `Lit`): cold until lit; then a `LightSource` of `brazier_radius` and
  an on switch, for good. `Lit = true` places it already lit.
  - **Lit by** a `Struck` (a swing from any direction) or by a live flare touching its body.
    A lit brazier ignores both.
  - **Saved by iid**: lit stays lit when its room reloads and after quitting and continuing; a
    lit brazier in an unloaded room still powers its targets (the save format does not change).
  - It lights its surroundings like any light: it refills the ember, burns Gloomcrawlers,
    draws Wisp-eaters and counts for photocells and lightforms.
- **Bell** (`Targets`): a swing rings it. For `bell_pulse` seconds after the last ring it is an
  on switch (a pulse; another ring restarts it). Every enemy within `bell_radius` px of the
  bell is stunned for `bell_stun` seconds: it stops, falls and cannot hurt by contact, as when
  staggered, then resumes. A bell does not move and is not saved.
- **Feedback**: lighting a brazier plays an ignite sound, a bell a ring and a small screen shake.
  Sprites show the lit brazier, the powered photocell and the ringing bell.
- Existing `Brazier` entities are cold unless placed with `Lit = true`; `Enemy_Yard`'s is.

## Tuning parameters
`content/feel.toml`, `[switches]`.

| Name | Default | Notes |
|---|---|---|
| brazier_radius | 72 | px; the light a lit brazier gives |
| bell_radius | 80 | px; enemies this close to a ringing bell are stunned |
| bell_stun | 2.0 | seconds |
| bell_pulse | 1.5 | seconds a bell's signal stays on |
| bell_trauma | 0.15 | screen shake on ringing |

A photocell's `Threshold` (0 to 1) is a level field, default 0.4: the player's lantern, radius
56, reaches it from 34 px, a lit brazier from 43 px.

## Acceptance criteria
- [x] A photocell is on while the light at it is at least its threshold and off otherwise: from
  the lantern, a flare, or a lit brazier; a door it targets follows.
- [x] A swing, from any direction, lights a cold brazier once; it then gives light and powers
  its targets.
- [x] A flare touching a cold brazier lights it; a burnt-out flare does not.
- [x] A lit brazier stays lit when its room reloads and after quitting and continuing, and powers
  its targets while its room is unloaded.
- [x] Ringing a bell stuns enemies within its radius, not those outside, for `bell_stun` seconds;
  a stunned enemy cannot hurt by contact and resumes after.
- [x] A bell powers its targets for `bell_pulse` seconds after a ring.
- [x] `Signal_Lab` has one of each wired to a door.

## Tests
`tests/unit/game/test_switches.py` drives the systems on a small world;
`tests/integration/test_switches.py` plays `Signal_Lab`: swinging a brazier lit and through its
photocell door, a flare, a bell stunning a Clockrat, and a quit and continue.
