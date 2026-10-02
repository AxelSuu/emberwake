# The Sunken Quarter

Area 1 and the vertical slice: 20 rooms, 30 to 40 minutes on a first run. Built in M9 (greybox)
and M10 (art and audio). Design rules are in the [GDD](../gdd.md#level-design-rules).

## Mood

A clockwork district at night, flooded to the knees. Dead lamp posts lean over black water;
posters peel off brick; gears stick out of the walls. Darkness is ink and plum, water a cold
teal, light a warm amber. Backdrops: `ruins` for the streets, `cavern` underground, new `cistern`
and `clocktower` presets.

## Arc

1. **Wake.** Awaken at the bottom of a dry well, learn to move, relight the first beacon.
2. **Streets.** Light lamps with the swing, meet Clockrats, cross water with the dash. Meet the
   Tinker, who gives you flares.
3. **Underways.** Dark rooms, Gloomcrawlers, doors, plates, photocells and lightforms. Come up
   into Market Square and open the shortcut back to the Tinker.
4. **Market Square (hub).** The Keeper explains: the way down to the Cistern needs both Quarter
   Lamps lit. Quill sells the map, Trial doors open.
5. **Two branches, either order.** The Clocktower (vertical, Gearbugs, crumbling platforms, the
   Clockrat King, Quarter Lamp A) and the Sluice (water, valves, Drip Lurkers, crates, Quarter
   Lamp B).
6. **The Cistern.** Descend, relight the last beacon, fight the Lamprey.
7. **The Great Lamp.** A lift carries you back up into Market Square; the Great Lamp burns, the
   streets light up lamp by lamp and the Quarter gets its color back. The way on to Brass
   Gardens is in sight but needs the Wickline.

## Map

```
                                     [Clock Face] A ...> Brass Gardens (Wickline)
                                           |
                                    [Clocktower Stair]
                                           |
                                       [Belfry]               [Trial Gate]
                                           |                       |
 [Well Climb]--[Lamp Row]--[Tinker's Nook] <=| [Market Square] |---+---[Sluice]--[Pump House] B
    |    :                       |                  |                     |
 [Wake]  [Old Guild]       [Gloom Cellar]    [Cistern Gate]          [Rat Warren] ...> Tidal Works
                                 |                  |
                           [Lever Hall]        [Cistern]  the Lamprey
                                 |                  .
                           [Cistern Shaft]          . lift, after the boss
                                 |                  .
                           [Plate Room]--[Photocell Gallery]--> up into Market Square
```

`--` and `|` are open passages, `<=|` a shortcut door opened from the right, `:` a secret behind
a cracked wall, `...>` a way that needs a later ability, A and B the Quarter Lamps.

Cells (top-left `[x, y]` in `levels/src/world.toml`), fixed so room batches can be built in
parallel. Two sizes differ from the table below so the Underways come back up into the Square:
the Plate Room is 2x1 and the Photocell Gallery 3x3, its top opening into the Square's floor.

```
 x:  0  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17
 y0                          CF CF
 y1                          CF CF
 y2                          CS
 y3                          CS
 y4                          CS
 y5                          CS
 y6                          BE BE
 y7                          BE BE
 y8     WC LR LR LR LR TN TN MS MS MS MS TG TG
 y9     WC OG       GC GC    MS MS MS MS SL SL SL SL PH PH
 y10    WC       LH GC GC PG PG PG CG CG       RW RW
 y11 WK WK       SH       PG PG PG CI CI CI
 y12 WK WK       SH PR PR PG PG PG CI CI CI
```

| Room | Cell | Size | | Room | Cell | Size |
|---|---|---|---|---|---|---|
| Wake | [0, 11] | 2x2 | | Market_Square | [8, 8] | 4x2 |
| Well_Climb | [1, 8] | 1x3 | | Trial_Gate | [12, 8] | 2x1 |
| Old_Guild | [2, 9] | 1x1 | | Belfry | [8, 6] | 2x2 |
| Lamp_Row | [2, 8] | 4x1 | | Clocktower_Stair | [8, 2] | 1x4 |
| Tinkers_Nook | [6, 8] | 2x1 | | Clock_Face | [8, 0] | 2x2 |
| Gloom_Cellar | [5, 9] | 2x2 | | Sluice | [12, 9] | 4x1 |
| Lever_Hall | [4, 10] | 1x1 | | Pump_House | [16, 9] | 2x1 |
| Cistern_Shaft | [4, 11] | 1x2 | | Rat_Warren | [14, 10] | 2x1 |
| Plate_Room | [5, 12] | 2x1 | | Cistern_Gate | [10, 10] | 2x1 |
| Photocell_Gallery | [7, 10] | 3x3 | | Cistern | [10, 11] | 3x2 |

Codes are the rooms' initials (CF Clock Face, CS Clocktower Stair, PR Plate Room, PG Photocell
Gallery, CI Cistern, CG Cistern Gate). Only touching edges can connect; every other shared edge stays a wall.

Built passages of the Underways (tiles within each room, 0-based; a "pit" is open floor with a
one-way plank at its foot that the player drops through with Down and Jump, and climbs back out of):

| Seam | Tiles |
|---|---|
| Lamp Row to Tinker's Nook | Nook west wall (col 0), rows 6 to 8; floor from row 9 |
| Tinker's Nook to Market Square | Nook east wall (col 39), rows 6 to 8, floor from row 9. A barred Door `d` (col 38, rows 6 to 8) is wired to nothing; the Square opens it with `Targets = ["Tinkers_Nook:d"]` on a lever or FlagSwitch. The Square's west wall (col 0) must be open at rows 6 to 8 of its top-left cell |
| Tinker's Nook to Gloom Cellar | Nook pit, cols 10 to 12, rows 9 to 10, over Gloom Cellar cols 30 to 32 of row 0, a one-way plank |
| Gloom Cellar to Lever Hall | Gloom west wall (col 0), rows 16 to 18; Lever Hall east wall (col 19), rows 5 to 7; floor from row 19 and row 8 |
| Lever Hall to Cistern Shaft | Lever Hall pit, cols 1 to 3, rows 8 to 10 (plank on row 10), over Cistern Shaft cols 1 to 3 of row 0 |
| Cistern Shaft to Plate Room | Shaft east wall (col 19), rows 17 to 19, floor rows 20 to 21; Plate Room west wall (col 0) must be open at rows 6 to 8, floor rows 9 to 10, with a PlayerStart within 6 tiles. A Door (col 17, rows 17 to 19) inside the Shaft shuts that exit until the Shaft's lever (once) is pulled |

The lab keeps its own copies of the greybox rooms as `Lab_Lever_Hall` and `Lab_Plate_Room` (and
`Shaft`), so the Quarter's `Lever_Hall` and `Plate_Room` do not clash with them.

## Rooms

Sizes in GridVania cells (one cell is 20x11 tiles, half the screen each way).

| # | Room | Cells | Role | Contents |
|---|---|---|---|---|
| 1 | Wake | 2x2 | Start, rest | Cold beacon, intro cutscene, signposts for move and jump, Echo 1 (a lamplighter's last round; the ghost walks to the first lamp) |
| 2 | Well Climb | 1x3 | Teach wall jump | Embers as breadcrumbs up the shaft, a cracked wall with a hairline |
| 3 | Old Guild | 1x1 | Secret | Echo 2 (Orrin addresses the Guild), Lantern Shard 1 |
| 4 | Lamp Row | 4x1 | Teach swing, lamps, dash | Four dead lamp posts to light, first Clockrats, a water channel to dash over |
| 5 | Tinker's Nook | 2x1 | Rest, shop | Beacon, the Tinker (shop; gives flares on first talk), barred door east (shortcut from the Square), hatch down |
| 6 | Gloom Cellar | 2x2 | Teach darkness | Gloomcrawlers, a brazier the swing ignites, Lost Light 1 to lead through the dark, one telegraphed Drip Lurker |
| 7 | Lever Hall | 1x1 | Teach levers and doors | Reworked from the greybox room; Clockrats behind the door |
| 8 | Cistern Shaft | 1x2 | Vertical link | Reworked `Shaft`; one-ways, Drip Lurkers under dark ledges |
| 9 | Plate Room | 1x1 | Teach plates and crates | Reworked; a crate to push onto the plate |
| 10 | Photocell Gallery | 3x1 | Teach flares on photocells, lightforms | Flare a photocell to open a door; lightforms over spikes; exit up into the Square |
| 11 | Market Square | 4x2 | Hub | Beacon, Keeper Hesper, the cold Great Lamp, grate down to the Cistern Gate, shortcut door west, Quill (after the Belfry) |
| 12 | Trial Gate | 2x1 | Optional | Trial doors for Sprint and Pits |
| 13 | Belfry | 2x2 | Test lamps under threat | Wisp-eaters snuff the lamps you light; a bell stuns them; Quill sells the map; Lantern Shard 4 behind a lamp hook (Wickline) |
| 14 | Clocktower Stair | 1x4 | Test wall jump, teach pogo | Gearbugs, crumbling platforms, hazard bulbs to pogo off, Lost Light 2 |
| 15 | Clock Face | 2x2 | Elite, Lamp A | Clockrat King encounter, Quarter Lamp A, Lantern Shard 3 at the top (pogo route), a lamp-hook gap east (Brass Gardens) |
| 16 | Sluice | 4x1 | Test dash and flares | Flooded channels, valves (levers) that drain sections for good, Drip Lurkers, crates, Lost Light 3 |
| 17 | Pump House | 2x1 | Twist: plate and photocell together, Lamp B | Quarter Lamp B, Oil Flask |
| 18 | Rat Warren | 2x1 | Optional arena | The old `Enemy_Yard`, now connected: an encounter of three waves, Lantern Shard 2; deep water down (Bell Jar, Tidal Works) |
| 19 | Cistern Gate | 2x1 | Pre-boss rest | Door that opens on Lamps A and B (mode all), beacon, Echo 3 (the night the Lantern went out) |
| 20 | Cistern | 3x2 | Boss | The Lamprey; after it, Echo 4 (the fuel line, and what it burned) and the lift up to the Square |

## Beacons and rest

Beacons in Wake, Tinker's Nook, Market Square, Cistern Gate, plus Quarter Lamps A and B (beacons
that also power the Cistern Gate door). No stretch of the critical path has more than five rooms
without one. Lamp posts fill the gaps: 4 in Lamp Row, 3 in the Belfry, 2 to 3 in most others.

## Teach, test, twist

| Mechanic | Teach | Test | Twist |
|---|---|---|---|
| Wall jump | Well Climb | Clocktower Stair | Clock Face, with crumbling platforms |
| Dash | Lamp Row (water gap) | Photocell Gallery | Sluice, under Drip Lurkers |
| Swing | Lamp Row (lamps, Clockrats) | Gloom Cellar | Clocktower (Gearbugs) |
| Pogo | Clocktower Stair (hazard bulbs) | Clock Face (Shard route) | Lamprey, phase 2 |
| Lamps | Lamp Row | Belfry (Wisp-eaters snuff them) | Cistern (the Lamprey snuffs them) |
| Darkness, flame, kindle | Gloom Cellar | Sluice | Cistern |
| Flares | Tinker's Nook (given) | Photocell Gallery | Belfry (decoy), Sluice (Drip Lurkers) |
| Levers and doors | Lever Hall | Cistern Shaft | Cistern Gate (two lamps, mode all) |
| Plates and crates | Plate Room | Sluice | Pump House |
| Photocells, lightforms | Photocell Gallery | Belfry | Pump House |

## People

| NPC | Where | Changes |
|---|---|---|
| The Tinker | Tinker's Nook | Gives flares on first talk. After the Great Lamp, moves to a stall in Market Square. |
| Keeper Hesper | Market Square | An old lamplighter's ghost who keeps the hub beacon. Explains the Quarter Lamps; rewards rescued Lost Lights (1: 50 embers, 2: flare pouch, 3: Oil Flask). |
| Quill | Belfry, then Market Square | A clockwork owl, the cartographer. Sells the Quarter map; after the Lamprey waits at the road to Brass Gardens. |
| Lost Lights | Gloom Cellar, Clocktower Stair, Sluice | Small spirits. Each follows you until you reach a beacon, then waits in Market Square. Lost if you die on the way; it goes back where you found it. |

## Story beats

- **Intro** (Wake): black screen, a beacon flickers, the spirit forms, the camera pulls out of
  the well. Skippable, as every cutscene.
- **Lamprey reveal** (Cistern): ripples, a lure light like a lamp, then the head.
- **Great Lamp** (Market Square): the light runs along the streets lamp by lamp, the grade warms
  room by room, the Tinker and Quill move. Ends on the road to Brass Gardens.

## The Lamprey

A skeletal eel coiled in the flooded Cistern (rig and IK from M7, behavior tree from M9).
Arena: three platforms over black water, four lamp posts, two photocells wired to sluice gates.

1. **Lure.** It surfaces and lunges at the brightest light. Throw a flare near a wall or a lamp
   post: it lunges, bites stone and is stunned; swing its glowing lure.
2. **Dark water.** It snuffs the lamps one by one. Relight them while it circles; pogo off its
   back as it breaches between platforms.
3. **Drain.** Its lunges break the photocells' casings; light them and the sluice gates drain
   the arena. On the floor it thrashes, with short windows to hit its head.

On death: hitstop, flash, the water drains out of the Quarter's lowest rooms (a flag), the lift
wakes up.

## Later abilities

Spots that bring the player back after the slice:

| Room | Needs | Reward |
|---|---|---|
| Belfry | Wickline | Lantern Shard 4 |
| Clock Face | Wickline | The road to Brass Gardens |
| Rat Warren | Bell Jar | The way down to Tidal Works |
| Gloom Cellar | Shutter | A shadeform stair to the Violet lens |
| Lamp Row | Ember glide | A rooftop cache: embers and a flare pouch |
| Market Square | Shadow-step | The Guild vault, the way into the Gloam |

## The greybox rooms we have

| Today | Becomes |
|---|---|
| Lever_Hall, Shaft, Plate_Room | Lever Hall, Cistern Shaft, Plate Room (reworked). The lab keeps `Lab_Lever_Hall`, `Lab_Plate_Room` and `Shaft` for tests |
| Enemy_Yard (not connected to anything) | Rat Warren, connected to the Sluice |
| Trial_Sprint, Trial_Pits | Trials behind the Trial Gate's doors, kept off the map |
| Test_Room, Return_Hall, East_Passage, Upper_Room | The lab: a dev region far off the map, kept for tests and `--room` |
