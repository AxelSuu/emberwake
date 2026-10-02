# M9 plan: The Sunken Quarter

**Goal.** Turn the systems into a game: the first area, from waking up to beating its boss,
playable from start to end in greybox. M9 is done when:

1. A new game starts in Wake, and a first-time player reaches and beats the Lamprey and lights
   the Great Lamp without dev tools, in 30 to 40 minutes.
2. The player fights with the lantern, heals with flame, loses embers on death and can win them
   back.
3. Everything the player changes stays changed: lamps, walls, shortcuts, doors, pickups, NPC
   places, abilities. Quitting and continuing proves it.
4. A map screen shows the rooms you have seen and the Quarter once you buy it.
5. Every room passes the world validator, and bots cover the critical path.

Art stays placeholder except an **art proof** (Wake, Well Climb, Lamp Row, the player and the
Clockrat in real pixel art), which starts M10 early so the style is settled before mass
production. The area itself is designed in [world/sunken-quarter.md](../world/sunken-quarter.md);
the rules are in the [GDD](../gdd.md).

## Where we are

The engine is ahead of the game. Done: movement, rooms and streaming, prefabs, signals, beacons
and saves, software lighting with shadows, shafts and post effects, particles, UI and menus,
settings and rebinding, i18n, combat basics, three enemies, flares, light rules, animation, rig
and IK, cutscenes, dialogue and shop, Trials with ghosts, achievements, cosmetics and assist.

What the player can actually do is thin:

- **No attack.** Nothing hurts Clockrats or Wisp-eaters, so the Exterminator achievement can only
  come from Gloomcrawlers burning.
- **Two worlds.** Seven connected greybox rooms around `Test_Room`; `Enemy_Yard` (the three
  enemies, the Tinker, the brazier, lightforms) sits one cell below with no way in except
  `--room`. The Trial rooms are reached from the menu.
- **No goal.** No ability gating, no boss, no story beyond five lines from the Tinker.
- **Rules that undercut each other.** Flares are unlimited (0.6 s cooldown) and refill the ember,
  so darkness has no bite; meanwhile ember at zero kills outright, a second death bar next to
  health. The HUD shows ember but not health.
- **Unused capability.** No art assets (`art/` does not exist; the pxl, atlas, autotile and
  normal tools have nothing to build), three sound effects, no music. Rig, IK and cutscenes are
  not used in play.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | The real world starts in `Wake`. Test and dev rooms move to a **lab** region far off the map, kept for tests and `--room`. | One world for players, stable rooms for tests. |
| D2 | **Health is the only way to die.** At zero flame the lantern gutters (smaller light, 1 damage per 4 s) instead of killing. | One death bar; darkness stays a pressure. |
| D3 | **Abilities and items are data**: an `Abilities` set and an `Inventory` of counts, saved in the slot, granted by pickups and dialogue actions, checked by gates. | Content decides progression without code. |
| D4 | **Flags drive world variants**: any entity can carry `Requires` and `Unless` conditions (the dialogue syntax), checked at spawn and when flags change; a `FlagSwitch` is a signal source. | NPCs move, rooms change after events, without one-off code. |
| D5 | **Save v2** holds abilities, inventory, the Cinder, map purchases and per-area light; every later shape change gets its migration. | ADR 0009. |
| D6 | **Lamps under a lit beacon are permanent**; others can be snuffed by light-eaters. | Beacons matter beyond saving; light-eaters threaten progress. |
| D7 | **Bosses use a small behavior tree** (`engine.core.bt`); regular enemies keep FSMs. | Architecture plan; FSMs get unwieldy for three-phase fights. |
| D8 | **Areas are a level field** (`Area`); banners, the map, music and light % key off it. | One place to group rooms. |
| D9 | **Art waits for the greybox**, except the art proof. | Art on rooms that still change is thrown away. |

Answered 2026-10-02: the defaults (in bold), all of them. Also asked for: a how-to-play screen
with the controls, many art ideas to iterate on, and animation, lighting and shaders as a big
focus (so the GL backend, #23, goes to M10 rather than after 1.0).

| # | Question | Options |
|---|---|---|
| Q1 | Death model | **Health death: back to the last beacon, embers dropped as a Cinder to recover. Hazards: 1 damage and back to the room entrance.** / Celeste: no penalty at all / harsher: lose embers outright |
| Q2 | Names for the two "embers" | **Meter: Flame. Currency: embers.** / meter Oil / currency Glims |
| Q3 | Flare limits | **Charges (2 to start, pouches add more), refilled in light and at beacons** / each throw costs flame / unlimited with a cooldown, as now |
| Q4 | Who draws | **Claude authors first-pass sprites as `.pxl`, checked by screenshots; you refine any in Aseprite** / you draw everything / CC0 packs as stand-ins |
| Q5 | Music | **A small TOML tracker (`tools/music`) that renders stems, chiptune-flavored, like the sfx tool** / you compose / CC0 tracks / no music until later |
| Q6 | Story and names (Vesper, Hesper, Quill, Orrin, the Gloam) | **Working names, change any time** / you name things |
| Q7 | Milestones on GitHub | **Insert M9 to M13 as content milestones, rename "M9 Ship" to "M14 Ship"; move #51 and #55 to M9, #47 to M10, #53 to M11, #23 to post-1.0** / keep M9 Ship and give the content phases another prefix |
| Q8 | Swing keys | **C and J (C leaves jump: Z/Space jump, X/K dash, C/J swing, F/Q flare); settings v7 migrates** / V and J, nothing moves |
| Q9 | Kindle input | **Hold Down for 0.8 s, grounded and still** / hold Interact with nothing in reach |

## Work breakdown

Four passes, each opening the next; rooms grow alongside, a few at a time, as soon as the
systems they use exist. One PR per letter, branch `m9/<issue>-<slug>`, stacked when it depends on
an unmerged PR.

```
 Pass 0  O lab ─────────────┬─► U1 ─► U2 ─► U3 ─► U4 ─► U5   rooms, 4 at a time
         V dev tools ───────┘
 Pass 1  A swing ──┬─► H lamps ─► I photocells, braziers, bells
                   ├─► J breakables, crumbling
                   └─► Q Drip Lurker, Gearbug ─► R Clockrat King ─► M encounters
         B HUD
         C light rules v2 ─► D death and Cinder
         E abilities, inventory, save v2 ─► F flags ─┬─► S NPCs
                                                     └─► N Echoes, signs, Lost Lights, Trial doors
 Pass 2  G areas ─► T map screen        K crates      L lifts        P world validator (E, F)
 Pass 3  W behavior trees ─► X Lamprey ─► Y story beats
 Art     Z art proof (independent, M10 pulled forward)
```

| PR | Issue | Size (est.) | Depends on |
|---|---|---|---|
| O | #111 Lab region: dev rooms off the map, `Wake` as the start | ~150 | |
| V | #112 Dev tools: room warp, flag and ability toggles, `--flags` | ~200 | |
| A | #114 Spec + lantern swing: swing, pogo, recoil, `Struck` events | ~500 | |
| B | #115 HUD: health pips, flame, flares, embers, area banner slot | ~300 | |
| C | #116 Light rules v2: gutter, flare charges, kindle, "Flame" | ~400 | |
| D | #117 Death and recovery: beacon respawn, Cinder, hazard damage, enemy reset | ~400 | C |
| E | #118 Abilities, inventory, grant pickups, save v2 | ~400 | |
| F | #119 World flags: `Requires`/`Unless`, `FlagSwitch`, `SetFlag` trigger | ~300 | E |
| G | #120 Areas: `Area` and `Music` fields, banners, light % and saturation | ~300 | |
| H | #121 Lamp posts: lit by the swing, protected by beacons, snuffed by Wisp-eaters | ~350 | A, G |
| I | #122 Photocells, ignitable braziers, bells as signal sources | ~300 | A |
| J | #123 Breakable walls, crates, pots; crumbling platforms | ~400 | A |
| K | #124 Pushable crates (pymunk props) that weigh plates | ~250 | #2 spike |
| L | #125 Moving platforms and lifts driven by signals | ~500 | |
| M | #126 Encounters: arena locks, waves, rewards | ~350 | R |
| N | #127 Echoes, signposts, Lost Lights, Trial doors | ~500 | F |
| P | #128 World validator: reachability by ability, entrances, flags | ~350 | E, F |
| Q | #129 Drip Lurker and Gearbug | ~450 | A |
| R | #130 Clockrat King | ~300 | Q |
| S | #131 Keeper Hesper, Quill, NPC stages, dialogue `give` | ~350 | F |
| T | #55 Map screen | ~450 | G |
| U1-U5 | #132 to #136 The 20 rooms, four per PR, with bots | ~300 each | O, then what they use |
| W | #137 Behavior trees in `engine.core.bt` | ~250 | |
| X | #51 The Lamprey, in two or three PRs | ~900 | W, H, I |
| Y | #138 Story beats: intro, Lamprey reveal, Great Lamp, credits stub | ~350 | X |
| Z | #139 Art proof: sprite bank, tileset, three dressed rooms | see [art plan](art-audio.md) | |
| Tips | #113 How to play: controls and tips screen | ~200 | |
| Art | #140 Art lab: idea sheets to iterate toward good designs | ongoing | Z |
| Anim | #141 Animation: entity animator, player clips, secondary motion | ~500 | Z |
| Light | #142 Lighting: emissive sprites, colored lights, light budget | ~400 | |

About 30 PRs. Each new mechanic starts as a spec in `docs/specs/` (swing, light rules v2, death
and recovery, lamps, flags, encounters, Lost Lights, the Lamprey).

## Design per issue

### O, V: the lab and dev tools

Dev rooms move to cells far right of the real map (x of 60 and up) so they never touch it;
`DEFAULT_ROOM` becomes `Wake` and the greybox tests keep their rooms. Dev tools (only with
`--dev`): F6 opens a room warp list; F7 a list of flags and abilities to toggle; `--flags a=1,b`
seeds a session. Rooms get tested by warping, not by walking from Wake.

### A: lantern swing

New action `swing`. A `Swing` component with a cooldown and a direction (forward, up, or down
when airborne); its hitbox comes from the `player_swing*` clips in `content/animations.toml`
(frame-tagged hitboxes already exist). On a hit: 1 damage, knockback, 2 ticks of hitstop,
recoil on the player, sparks. A down swing that hits an enemy or a `Bouncy` thing (hazard
bulbs) sets the vertical speed to a jump and refills the dash. Every hit publishes
`Struck(target, direction)`, so lamps, braziers, breakables and bells react without the swing
knowing them. Tuning in `feel.toml` under `[swing]`.

### B: HUD

`game/render/hud.py`: lantern-shaped health pips, a flame wick bar that pulses when low,
flare charges, and an ember count that appears when it changes and fades. A slot for area
banners (G). Drawn after post effects so grading never tints it; hidden in cutscenes.

### C, D: light rules v2, death and recovery

Gutter state on the `Ember` component (player text says Flame): the lantern radius drops to a
third and a timer deals 1 damage every 4 s. `FlareKit` gets charges, refilled at 1 per 2 s in
light and fully at beacons. Kindle: hold Down for 0.8 s, grounded and still, at least 30 flame:
heal 1 with a squash and a burst. Health death respawns at the continue beacon with full
health; the carried embers drop as a `Cinder` entity in the room (saved in the slot, one at a
time). Hazards deal 1 damage and send you to the entrance as now. Resting at a beacon resets
the regular enemies of loaded rooms.

### E, F: abilities, inventory and flags

`Abilities` (set of names) and `Inventory` (counts: shards, flasks, keys, pouches) live in the
save, which goes to version 2 with a migration. A `Grant` prefab (an ability or item pickup with
a pickup fanfare) and the dialogue action `give:<thing>` add to them; Dash and Flare check
`Abilities` (dash stays a starting ability). Any entity can carry `Requires` and `Unless` fields
parsed with the dialogue's condition syntax; the spawner skips entities whose conditions fail,
and a flag change respawns or despawns them live. `FlagSwitch` is a signal source that is on
while its condition holds; a `SetFlag` trigger sets a flag when touched.

### G, T: areas and the map

Level fields `Area` (default `quarter`) and `Music` (stem set). Entering a new area shows its
banner. Light % per area = (lit lamps + lit beacons + Lost Lights rescued + Echoes found) over
their totals, computed from `WorldState` and the level files; it scales the grade's saturation.
The map screen (a pause tab) draws rooms from their LDtk rects: visited rooms solid, unvisited
rooms of a bought map as outlines, with icons for beacons, NPCs, the Cinder and you.

### H, I, J: lamps, light switches, breakables

A lamp post is a `LightSource` plus a `Lamp` (lit, protected) persisted by iid; a `Struck` lights
it. A Wisp-eater's brain picks the nearest unprotected lit lamp as a target and snuffs it on
arrival. Photocells are `Switch`es whose state is `light_at >= threshold`; a brazier lit by a
`Struck` or a flare touching it becomes a `LightSource` and a switch. A bell on `Struck` stuns
enemies in a radius and pulses its targets. Cracked walls work like doors: they own cells, go
empty on a `Struck` and stay broken. Crates and pots break into embers. Crumbling platforms are
one-way cells that clear 0.5 s after the player lands and come back after 2 s.

### K, L: crates and lifts

Crates are pymunk props (the fallback backend covers the web if the #2 spike says no) that a
plate's trigger counts. Lifts and moving platforms are bodies on a path between nodes, moving
while powered (or looping); the player standing on one is carried by its velocity, and the
sub-stepped collision treats it as solid from above.

### M, Q, R: enemies and encounters

Drip Lurker: ceiling state, drop when the player is below and the spot is unlit, ground state,
climb back. Gearbug: patrol with an armored front (hits from the front only recoil), a vent cycle
during which it is open, and a back you can pogo. Clockrat King: a big Clockrat with a crown lamp
(a light source), charges, summons rats from spawn markers, topples when hit on the crown.
An `Encounter` entity closes its doors when the player enters its area, spawns waves of enemies
from markers and powers its targets when the last wave dies; cleared encounters stay cleared.

### N, S: people and lore

An Echo plays a stored replay (`content/echoes/<id>.json`) as a translucent ghost and shows a
line of text; seen Echoes count in the journal and light %. Signposts show a string with key
glyphs from the current bindings. A Lost Light follows the player with a short delay (a trail of
past positions); reaching a beacon rescues it (a flag), dying returns it home. Keeper Hesper and
Quill are dialogue graphs plus flag-gated placements per stage; Quill's shop sells the map.
Trial doors start their Trial and unlock it in the menu.

### P: world validator

Part of `just check`. Builds the room graph from the level files with each connection labelled
by what it needs (an ability, a door's sources, a one-way drop), then checks: every room is
reachable from Wake with the abilities available by then; nothing on the slice's critical path
needs a later ability; every entrance has a PlayerStart within a few tiles; every flag a
`Requires` reads is set somewhere; every wiring target exists.

### W, X, Y: the Lamprey and the story

`engine.core.bt`: sequence, selector, parallel, condition, action, cooldown and repeat nodes,
ticked with the blackboard of the entity. The Lamprey is a rig (head, jaw, lure, segments, fins)
whose segments follow the head with IK; its tree implements the three phases in the area doc.
Cutscenes reuse the coroutine player: intro in Wake, the reveal in the Cistern, and the Great
Lamp sequence that lights lamps in order of distance and sets the area's flags.

## Rooms

A room is done when: its ASCII and TOML compile; every entity is wired and validated; there is a
PlayerStart at each entrance; a bot proves the critical path through it (the traversal bots in
`tests/integration/test_greybox.py` are the model); you have played it once and its notes are
dealt with. Batches follow the critical path so each can be played from Wake:

| Batch | Rooms | Needs |
|---|---|---|
| U1 | Wake, Well Climb, Old Guild, Lamp Row | A, H, J |
| U2 | Tinker's Nook, Gloom Cellar, Lever Hall, Cistern Shaft | C, E, I, N |
| U3 | Plate Room, Photocell Gallery, Market Square, Trial Gate | K, S |
| U4 | Belfry, Clocktower Stair, Clock Face | Q, R, M |
| U5 | Sluice, Pump House, Rat Warren, Cistern Gate, Cistern | L, X |

## Testing

- Unit tests per system; scenario tests drive the gameplay scene headless with scripted input.
- Bots per room batch for the critical path, plus a test that a new game reaches the Square.
- A **golden run**: a recorded replay of the whole slice that must end with the Great Lamp lit.
  Re-recorded with `just golden` when rooms change; failing it means a softlock or a broken
  room. Determinism (fixed steps, seeded randomness) makes this possible.
- Save migration tests from v1 slots.

## Risks

| Risk | Mitigation |
|---|---|
| Scope: 30 PRs | Passes are playable on their own; rooms come in batches; cut the Rat Warren, Trial Gate and Old Guild first if needed |
| Many lights in a room slow the software backend in the browser | A light budget per frame (nearest N, the rest baked as static glow); extend `tests/bench` with a 12-lamp room |
| pymunk in pygbag (#2) | Crates work on the fallback prop backend |
| Lifts and kinematic collision | Spec first; carry the rider by the platform's displacement, tested with bots |
| Content churn breaks saves | Iids come from room and marker names: keep names stable; migrations for shape changes |
| Art proof shows the pxl route is too slow or too rough | Q4 fallback: you draw the key sprites, Claude does tiles and props |

## After M9

M10 dresses and scores the Quarter; M11 to M13 build Brass Gardens, Tidal Works and the Lantern
Spire; M14 ships. See the [roadmap](../roadmap.md).
