# Clockrat King

**Milestone:** M9  **Status:** draft  **Issue:** #130

## Goal
The Clocktower's elite: a big Clockrat that charges, calls rats and cannot be swung at from the
side. The player has to get above its crown (a jump, a pogo) to topple it, and then has a short
window to hurt it. Its crown lamp lights the arena. It is a regular enemy `Brain` (an FSM);
behavior trees are for bosses. Doors, arena and waves are the Encounter's job (#126), not this.

## Behavior

`Brain` kind `clockrat_king` in `game/enemies.py`, placed as the `ClockratKing` entity (32x32
body, pivot bottom centre). It gets health, a hurt box, a contact hit box and a `Guard` like the
other kinds. The prefab gives it a `LightSource`: the crown lamp, lit while it stands.

### Armor and the crown
Upright, the King is guarded from every side but above (`Guard` with `top` off): a swing from
level with it, or from below, clangs and recoils the player. A swing whose attacker is above the
King's middle (a down swing or pogo from over it, a jump-in swing) reaches the crown: it hurts
and topples the King at once, from any upright state. Hits take no knockback; it is too heavy.

### States
- **patrol**: walks at `king_speed`, turns at walls and ledges. When the player is within
  `king_sight` px ahead and roughly level it goes to rear. When `king_summon_every` seconds have
  passed since the last call, the player is within `king_alert` px and fewer than `king_rats_max`
  of its rats are alive, it calls instead.
- **rear**: stops and trembles for `king_rear` seconds, facing the player. A warning.
- **charge**: runs the way it faces at `king_charge_speed` for at most `king_charge_time` seconds,
  until a wall or a ledge. Then rest, turning around if it hit something.
- **rest**: stands for `king_rest` seconds, then patrol.
- **call**: stands for `king_call` seconds, then summons: up to `king_summon_count` rats (fewer
  if `king_rats_max` would be passed) appear at `RatSpawn` markers in its room, then patrol.
- **toppled**: knocked flat by a crown hit. Falls if it must, lies for `king_topple_time` seconds
  and then gets up into patrol. While down the lamp is out, its armor is off, so every swing
  hurts it, and contact does not hurt the player. A hit while down does not extend the time.

### Rats
A summoned rat is an ordinary Clockrat entity (not a placed one, so it has no iid and is never
saved) owned by the King. Which markers it uses, and which way each rat faces, come from a
`random.Random` seeded with the King's iid, so a replay summons the same rats. Markers are
considered in position order; each summon picks without repeating until all are used. Rats are
cleared as soon as their King is gone: killed, or its room unloaded.

### Defeat
Killing the King retires it by iid (`WorldState.removed`): it does not return when its room
reloads, after resting at a beacon or after quitting and continuing. Its rats vanish with it.
The save format does not change.

### Feedback
Toppling shakes the screen, throws dust and publishes `Toppled`; a call publishes `Summoned`
for each rat, drawn as a puff at the marker. Placeholder art: the King upright with a lit crown
lamp, and lying down with the lamp dark while toppled.

## Tuning parameters
`content/feel.toml`, `[enemies]`.

| Name | Default | Notes |
|---|---|---|
| king_hp | 10 | the crown hit that topples it costs 1 |
| king_speed | 28 | px/s patrolling |
| king_sight | 128 | px ahead that make it rear up |
| king_rear | 0.6 | seconds of warning before the charge |
| king_charge_speed | 150 | px/s |
| king_charge_time | 1.2 | seconds, at most |
| king_rest | 1.0 | seconds after a charge |
| king_alert | 224 | px sideways within which it calls rats |
| king_summon_every | 6.0 | seconds between calls |
| king_call | 1.0 | seconds standing before the rats appear |
| king_summon_count | 2 | rats per call |
| king_rats_max | 3 | rats alive at once |
| king_topple_time | 2.5 | seconds on its back |

## Acceptance criteria
- [ ] Swings from the side or below clang off an upright King: no damage, the player recoils.
- [ ] A hit from above (down swing or pogo) hurts the King and topples it; it takes no knockback.
- [ ] A toppled King takes every kind of swing, does not hurt on contact, has its lamp out, and
  gets up after `king_topple_time`, whatever hits it meanwhile.
- [ ] The King patrols, rears at the player and charges, resting after a wall, a ledge or the
  time limit.
- [ ] Calling spawns rats at `RatSpawn` markers in its room, never more than `king_rats_max` alive,
  the same way every time for the same iid.
- [ ] Its rats disappear when the King dies or its room unloads.
- [ ] Killing the King retires it: it stays dead after a room reload and after quit and continue.
- [ ] The crown lamp lights its surroundings while it stands and not while it is toppled.
- [ ] `King_Lab` (a lab room) holds a King and rat markers and can be reached with
  `--room King_Lab`.

## Tests
`tests/unit/game/test_enemies.py` drives `enemy_system` on a small `Yard`: the state cycle, the
crown rule with `combat_system`, rat counts, cleanup and determinism, retiring by iid with a
`Spawner`. `tests/integration/test_clockrat_king.py` loads `King_Lab`, topples and defeats the
King by swinging, and checks that the defeat survives a reload.
