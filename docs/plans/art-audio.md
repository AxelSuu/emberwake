# Art and audio plan

**Goal.** The Sunken Quarter looks and sounds finished (M10), with no code-drawn placeholder
left in it. It starts in M9 with an **art proof** that settles the style on three rooms before
anything is mass-produced. Rules for how things look are in the [art bible](../art-bible.md);
this plan is about what to make, in what order, and the tools still missing.

## Principles

- **Text first.** Sprites are `.pxl` files in `art/`, compiled by `just art` into `assets/`.
  They diff, review and lint like code, and Claude can author them (Q4 in the
  [M9 plan](m9-sunken-quarter.md)).
- **Never break the game.** A sprite bank looks sprites up by name and falls back to the
  placeholder art, so art lands one sprite at a time.
- **See it in place.** Every art PR comes with screenshots rendered headless from the real game,
  not only the sprite sheet.
- **Silhouette, then value, then color.** Every sprite must read as a flat ink shape at 1x.
- **Warm means light, and light means "you can use this".** Darkness is three or four values of
  cold plum, ink and teal. Amber and orange are kept for light sources, the lantern, embers and
  the one accent pixel that marks an interactable.

## Missing tools

In order; the first four are part of the art proof.

| # | Tool | What |
|---|---|---|
| 1 | Sprite bank | `game/render/bank.py`: name to surface or sheet from `assets/sprites/`, frame JSON to animation clips, placeholder fallback, F5 reload |
| 2 | Entity animator | An `Animator` for any entity (state to clip), fed by brains, switches and lamps; `sprite_system` picks frames |
| 3 | Tilesets | A `Tileset` level field (default per area); the chunk painter draws autotile blob sets (47 tiles) with seeded variants, one-way planks, spikes and animated water |
| 4 | Screenshots | `just shot <room>` renders a room headless to `build/shots/<room>.png` (dressed and lit), `just sheet` a contact sheet of every sprite; how Claude reviews its own art |
| 5 | Back walls | A back layer filled behind open cells inside the room, overridable with `<room>.back.txt` (windows, arches, none), darkened, lit by lights |
| 6 | Decor | Rules in `content/decor.toml` seeded by room iid: moss on top edges, drips and chains under ceilings, rubble at wall feet, posters on back walls; a `Decor` entity for hand placement |
| 7 | Emissive pass | The software backend adds emissive sprites after lighting, so eyes, flames and embers glow in the dark without the GL backend |
| 8 | Bitmap font | `art/ui/font.pxl`: a 5x7 glyph sheet with ASCII and åäö, a `BitmapFont` in `engine.ui`; replaces `pygame.font.Font(None)` everywhere and avoids the m5x7 license question |
| 9 | Authored parallax | PNG layers per area next to the procedural mist, pillars and skyline |
| 10 | Portraits | 32x32 faces in the dialogue box |
| 11 | Aseprite import | Art bible step 3, only if you draw (Q4) |

## Art proof (M9, issue Z)

Player (idle, run, jump, fall, dash, swing), Clockrat (walk, charge, hurt, death), lamp post
(dead, lit), beacon (cold, lit), the Quarter brick tileset, a back wall, six decor pieces, the
streets backdrop and the HUD icons. Dress Wake, Well Climb and Lamp Row with them.

Done when greybox and dressed screenshots of the three rooms sit side by side in the PR, you have
approved the style (or asked for changes and they are in), and the art bible records what was
settled: outline rule, shading steps, highlight placement, how much texture a tile carries.

## Sunken Quarter assets (M10)

| Group | Items | Size, px |
|---|---|---|
| Player | See the clips below | 16x24 |
| Enemies | Clockrat, Gloomcrawler, Wisp-eater, Drip Lurker, Gearbug: idle, move, attack, hurt, death each | 16x16 |
| Elite | Clockrat King: idle, charge, summon, topple, death | 32x24 |
| Boss | Lamprey rig parts: head, jaw, lure, 8 segments, fins; splash and breach effects | parts up to 32x32 |
| NPCs | Tinker, Keeper Hesper, Quill, Lost Light: idle and talk, plus portraits | 16x24, portraits 32x32 |
| Mechanisms | Lever, door, plate, photocell, bell, brazier, lamp post, beacon (cold, lit: 6 flame frames), lift, crumbling platform, shortcut door, Trial door | 16 to 48 |
| Pickups | Ember, Cinder, Lantern Shard, Oil Flask, flare pouch, Echo, Grant pedestal | 8 to 16 |
| Breakables | Cracked wall, crate, pot, with break frames | 16 |
| Tiles | Quarter brick, stone, wood planks (one-way), iron grate, spikes, water surface (animated), hazard bulb | 16 |
| Decor | Pipes, chains, gears, posters, windows, barrels, rubble, moss, drips, signs | 8 to 32 |
| Backdrops | `streets`, `cistern`, `clocktower`: 3 to 4 layers each | 640 wide |
| UI | Font, HUD (health pip full and empty, flame wick, flare, ember), dialogue frame, menu frame, map tiles and icons, key glyphs, achievement icons | 8 to 32 |
| FX | Swing arc, hit spark, dust, splash, ember sparks, smoke, flare trail | 8 to 16 |

About 120 sheets. The later areas reuse the structure with their own tiles, decor, enemies and
backdrops (about 60 sheets each).

## Player animation

| Clip | Frames | Events and boxes |
|---|---|---|
| Idle | 6 | Lantern sway |
| Run | 8 | `footstep` on contact frames |
| Jump, fall | 2 + 2 | Squash and stretch stay in code |
| Wall slide | 2 | Dust at the hand |
| Dash | 3 | Afterimages in code |
| Swing forward, up, down | 5 each | Hitbox on the active frames |
| Hurt | 2 | |
| Death | 6 | Lantern rolls away |
| Kindle | 4 | Loops while charging |
| Throw | 3 | `release` spawns the flare |
| Interact | 3 | |

## Music

- **Stems per area**, one key and tempo: `dark` (pad and drone, always on), `lit` (the melody,
  faded in when the room is lit and louder with the area's light %), `danger` (percussion while
  an enemy has seen you). `Audio.set_stems` already cross-fades. The Quarter's theme is the
  first, then a boss theme in two phases, the title theme, the Great Lamp sting and credits.
- **Source** (Q5): `tools/music`, a small tracker. TOML patterns of notes per channel, instruments
  from the sfx synth, rendered to OGG stems by `just music`, so music diffs and builds like
  everything else.

## Sound effects

Presets in `sfx/*.toml`, rendered by `just sfx` with pitch variants. Three exist (jump, land,
dash).

| Group | Sounds |
|---|---|
| Player | Footsteps per surface (stone, wood, metal, water), wall slide, swing, swing hit, pogo, hurt, death, kindle charge and heal, flare throw, low-flame heartbeat, gutter |
| World | Lever, door open and close, plate, photocell hum, brazier ignite, lamp ignite and snuff, bell, wall break, crate break, crumble, lift loop, splash, beacon relight, Great Lamp sting |
| Pickups | Ember (pitch rises in a chain), shard, flask, grant fanfare, Cinder recovered |
| Enemies | Per enemy: notice, attack, hurt, death; Clockrat King roar; Lamprey breach, lunge, bite, snuff, scream |
| People | Dialogue blips per NPC (a voice is a pitch and a wave), shop buy |
| UI | Move, accept, back, toggle, slider tick, achievement, map open |

## Ambience

Loops per room type under the music: drips, distant gears, wind in the clocktower, water lapping,
the hum of a lit beacon. Chosen by a level field `Ambience`, cross-faded like backdrops.

## Order of work in M10

1. Sprite bank and animator, if the art proof did not finish them.
2. The player's full sheet.
3. Tilesets, back walls and decor rules for every Quarter room.
4. Mechanisms, pickups and breakables.
5. Enemies, the Clockrat King, then the Lamprey's parts.
6. NPCs and portraits.
7. Backdrops.
8. UI: font, HUD, dialogue and menu frames, map, glyphs.
9. Effects.
10. Music stems, sound effects, ambience.
11. A polish pass room by room against screenshots.
