# Game design document

Living document. Mechanics get their own spec in `specs/` before implementation. Areas are
designed room by room in `world/`; what gets built when is in the [roadmap](roadmap.md) and
`plans/`. Names of places and people are working names until M9 Q6 is settled.

## Pitch

You are a lamplighter spirit in a drowned, lightless clockwork city. Carry your lantern through
the dark, relight the beacons and bring color back, one district at a time.

2D side-scrolling action-platformer, metroidvania structure, 640x360 pixel art, built around
**light as the core mechanic**.

## Pillars

1. **Light is gameplay.** Light reveals, protects, harms and builds. Every system asks "what does
   light do here?"
2. **Tight feel.** Responsive movement with forgiving inputs. Juice on every action.
3. **Earned color.** The world starts cold and desaturated; your progress literally repaints it.
4. **Replayable mastery.** Trials, medals, ghosts and stats reward going back.
5. **The city remembers.** Every lamp you light, wall you break and shortcut you open stays that
   way. Progress shows in the world, not only in menus.

## Core loop

Explore a dark room -> fight and solve with light -> light lamps on the way -> find the beacon
-> relight it (save, heal, the lamps around it become permanent, color returns) -> unlock an
ability or path -> backtrack through lit, safer streets -> new area.

The game has two speeds. New areas are tense: darkness drains your flame and shadows hunt you.
Lit areas are calm: lamps refill you and shadows avoid them. The player turns the first into the
second, and the map shows it.

## Story

The city of **Vesper** ran on light. The Lamplighters' Guild kept the Great Lantern burning at
the top of the Lantern Spire, and its light drove the city's clockwork, from the tide pumps to
the tower clocks. One night the Great Lantern went out. The pumps stopped, the sea came in, and
the dark grew things that eat light: the **Gloam**.

You are a lamplighter spirit, the last ember of the Guild, rekindled at the bottom of a dry well
by a beacon that flickered back on by itself. You carry a lantern and can relight what the Guild
left behind.

What the game reveals (Echoes, NPCs, the environment): the Great Lantern burned spirits. Every
ember in the city is a soul, and the Guild fed them to the flame. Orrin Vale, the Guild's master,
snuffed it to free them and became the **Hollow Lamplighter**, keeper of the dark. The Gloam is
what grew in the dark he made.

Endings, chosen at the Great Lantern:

| Ending | How | What happens |
|---|---|---|
| Kindle | Relight the Great Lantern | Vesper wakes fully restored. The spirits you carried burn, you among them. |
| Vigil | Refuse; needs every area's Great Lamp lit | The beacons you relit hold the city in a gentler, partial light. You stay as its lamplighter. |
| Dawn (secret) | Every Echo found, then spare Orrin | Together you make the beacons burn without spirits. Needs 100 % light. |

The story is told through short NPC dialogue, **Echoes** (ghost replays of a lamplighter's last
moments, played by the replay system), the environment (posters, statues, flooded homes) and at
most three cutscenes per area. No walls of text.

## Player verbs

| Verb | From | Notes |
|---|---|---|
| Run, jump | start | Coyote time, jump buffer, variable height, corner correction, apex hang |
| Wall slide, wall jump | start | |
| Ember dash | start | 8-direction, refills on ground or in light |
| Lantern swing | start | Melee arc forward, up or down. A down swing in the air bounces off enemies and hazard bulbs (pogo) and refills the dash. Ignites lamps and braziers, breaks cracked walls, crates and pots. |
| Kindle | start | Hold Down while grounded and still: spend 30 flame to heal 1 health. Cannot be done in the dark without the flame to spare. |
| Interact | start | Levers, NPCs, beacons, signposts, Echoes |
| Throw flare | Sunken Quarter (the Tinker) | Limited charges, refilled in light. A tumbling physics prop and a temporary light. |
| Wickline | Brass Gardens | A line of light that hooks lamp brackets: swing on it and pull light switches from afar |
| Shutter | Brass Gardens | Close the lantern: you give no light, flame drains faster, light-eaters lose you, shadeforms appear |
| Bell Jar | Tidal Works | The lantern burns underwater: swim and dive |
| Ember glide | Tidal Works | Hold jump in the air to glide; steam vents and lit braziers lift you |
| Light-bridge | Lantern Spire | Spend flame to cast a beam that hardens into a bridge for a few seconds |
| Shadow-step | Lantern Spire, late | Dash through darkness, from one unlit spot to another, through walls of shadow |

Each unlock answers "what does light do here?" and opens old areas: every area keeps 3 to 5
spots that need a later ability (Lantern Shards, Echoes, Lost Lights, shortcuts).

## Light rules

- **Flame** is the lantern's fuel (the code's `Ember` component; "embers" are the currency). It
  drains slowly in darkness and refills in light other than your own lantern.
- At zero flame the lantern **gutters**: its radius drops to a third, shadows grow bolder and you
  lose 1 health every 4 seconds until you reach light. It no longer kills on its own.
- Light sources: lit beacons, lamp posts, braziers, flares, powered lamps, glowing pollen (Brass
  Gardens), beams (Lantern Spire) and your lantern.
- Shadow creatures take damage over time in light and flee strong light.
- **Lightforms** exist only while lit; **shadeforms** only while dark (Shutter).
- **Lamp posts** light with a swing and refill flame. Light-eaters snuff lamps unless a lit
  beacon protects them; once the area's Great Lamp burns, its lamps are permanent.
- **Beacons**: save, full heal, refill flares, set the continue point and warm the area's grade.
- **Light %**: each area counts lit lamps and beacons, rescued Lost Lights and found Echoes. The
  map shows it, and the area's saturation follows it, so color returns step by step.

## Combat

- **Health** in pips: 3 at the start. The Tinker sells up to 3 more; every 3 Lantern Shards add
  one.
- **Swing**: 1 damage, about 0.3 s, knockback on the target and recoil on you, 2 ticks of
  hitstop, sparks. Hitting a wall or a shield gives recoil without damage.
- **Contact**: 1 damage, knockback, 1 s of invulnerability.
- **Death** (health): back to the last beacon. You drop your carried embers as a **Cinder** where
  you fell; touch it to take them back. Die again first and they are gone.
- **Hazards** (spikes, deep water, the void): 1 damage and back to the room entrance you came
  through, so retries stay fast. On your last pip it is a death.
- Enemies drop embers; shadow creatures drop a little flame instead.
- Regular enemies come back when their room reloads or you rest at a beacon; elites and bosses
  stay dead.

## World

Vesper is one GridVania map of five areas, about 80 rooms and 5 to 7 hours.

| Area | Look | Signature mechanic | Abilities | Enemies | NPCs | Boss |
|---|---|---|---|---|---|---|
| The Sunken Quarter | Flooded streets, dead lamps; ink and plum with amber light | Lamps, photocells, levers and plates | Flare | Clockrat, Gloomcrawler, Wisp-eater, Drip Lurker, Gearbug; Clockrat King (elite) | Tinker, Keeper Hesper, Quill, Lost Lights | The Lamprey |
| Brass Gardens | Glasshouses of verdigris brass; teal and gold | Phototropic vines grow toward light; glowing pollen | Wickline, Shutter | Mothling swarm, Thornspring, Shade; Moth Queen (elite) | The Gardener | Bloomhusk |
| Tidal Works | Pump halls and rust; deep blue and rust orange | Water level as world state: valves raise and lower water across rooms; steam vents | Bell Jar, Ember glide | Anglerlamp, Barnacle, Tidecrab, Eelings | Brine the diver | The Tidekeeper |
| Lantern Spire | White stone and gold, violet shadow | Mirrors and beams route beacon light; clockwork that turns only while lit | Light-bridge, Shadow-step | Mirror Knight, Sentinel, Hollow Acolyte | Orrin (a voice, then in person) | The Hollow Lamplighter |
| The Gloam (optional) | No light at all | Shutter, shadeforms and shadow-step only | Dawnglass lens | Gloam versions of earlier enemies | | The Gloam Heart |

The hub is **Market Square** in the Quarter: rescued Lost Lights gather there, NPCs move there as
the story goes on, and the Trial gate stands there. From Brass Gardens on, lit beacons in areas
whose Great Lamp burns form a fast-travel network.

## Bestiary

| Enemy | Area | Light | How to beat it |
|---|---|---|---|
| Clockrat | Quarter | Indifferent | Patrols, charges on sight; swing it, or let it charge into a wall and stun itself |
| Gloomcrawler | Quarter | Shadow: burns in light, flees strong light | Creeps up in the dark; light it, then swing |
| Wisp-eater | Quarter | Eats light: flies to the nearest flare or unprotected lamp and snuffs it | A flare is a decoy; swing it while it eats |
| Drip Lurker | Quarter | Hangs from dark ceilings, drops on whatever passes below unlit; retracts in light | Throw a flare ahead, or bait the drop and swing as it lands |
| Gearbug | Quarter | Indifferent; armored front, vents steam on a cycle | Pogo off its back, or swing while it vents |
| Clockrat King | Quarter, elite | A lamp on its crown lights its arena | Calls rats and charges; hits to the crown topple it |
| Mothling swarm | Gardens | Follows your lantern, snuffs flares, nibbles flame | Shutter to lose it, or lead it into a brazier |
| Thornspring | Gardens | Plant turret that shoots seeds at light | Approach shuttered |
| Shade | Gardens, Spire | Invisible in darkness; only visible and hittable when lit | Light it first |
| Anglerlamp | Tidal | Its lure looks like a beacon flame | Do not trust warm light underwater |
| Barnacle | Tidal | Wall turret that fires when lit | Pass dark, or flare it from cover |
| Tidecrab | Tidal | Shelled | Pogo |
| Eelings | Tidal | The Lamprey's brood; schools in water | Avoid or swing |
| Mirror Knight | Spire | Reflects beams and flares | Hit it from behind |
| Sentinel | Spire | Patrolling light cone; seen means an alarm | Shutter, or stay out of the cone |
| Hollow Acolyte | Spire | Throws dark flares: zones of anti-light that drain flame | Kill it before it throws, light the zone back up |

Bosses use behavior trees and their area's mechanic: the **Lamprey** lunges at the brightest
light in a flooded cistern, **Bloomhusk** opens only toward sun lamps, the **Tidekeeper** floods
and drains its arena, the **Hollow Lamplighter** uses your own abilities against you, and the
**Gloam Heart** fights in total darkness.

## Interactables

| Thing | State | Notes |
|---|---|---|
| Lever, door, pressure plate | done | Signals with any/all/invert (ADR 0016) |
| Beacon, ember, lightform, brazier, goal | done | |
| Lamp post | planned | Light source lit by a swing; persistent under a lit beacon; counts toward light % |
| Photocell | done | Signal source, on while lit (flares, lamps, beams) |
| Ignitable brazier | done | Swing or flare lights it; a signal source while lit |
| Bell | done | Swing to ring: stuns nearby enemies, sends a signal pulse |
| Cracked wall, crate, pot | planned | Breakable; secrets and embers; walls stay broken |
| Crumbling platform | planned | Falls a moment after you land, comes back |
| Pushable crate | planned | Physics prop that weighs plates down |
| Moving platform, lift | done | Driven by signals; carries the player |
| Shortcut door | planned | Opens from one side only, stays open |
| Flag gate | planned | An entity exists only while a flag is set (or unset): NPCs move, rooms change after events |
| Encounter | planned | Locks its doors, spawns waves, powers its targets when cleared |
| Echo | planned | A ghost replays a lamplighter's last moments: lore, sometimes a hidden route |
| Signpost, note | planned | Readable text, with key glyphs for tutorials |
| Lost Light | planned | A spirit that follows you to the nearest beacon, then moves to the hub |
| Trial door | planned | Starts a Trial from the world |
| Later areas | planned | Phototropic vine, pollen pod, valve and water level, steam vent, lamp hook, mirror, beam receiver, shadeform |

## Collectibles and economy

| Item | Per area | Use |
|---|---|---|
| Embers | many | Currency from pickups, enemies, crates and pots. Dropped as a Cinder on death. |
| Lantern Shard | 3 to 4 | Three make one more health pip |
| Oil Flask | 1 to 2 | +20 maximum flame |
| Flare pouch | 1 | +1 flare charge (also sold by the Tinker) |
| Lens | 1 to 2, from Brass Gardens | Colored lantern glass, one equipped at a beacon: Amber (wider light), Mint (slower drain), Violet (reveals Shades and secrets), Rose (beacons and kindling heal more), Cinderglass (the swing burns) |
| Echo | 4 | Lore; all of them open the Dawn ending |
| Lost Light | 3 to 4 | Rescued spirits gather in Market Square; the Keeper rewards milestones |
| Guild key | rare | Opens a specific locked door |

Shops: the **Tinker** sells heart lanterns (+1 health), oil (+flame), flare pouches and later
lenses. **Quill** sells each area's map.

## Statefulness

| What | Rule |
|---|---|
| Kept forever (saved by iid or flag) | Once switches, beacons, lamps under a lit beacon, broken walls, opened shortcuts, pickups and collectibles, elite and boss kills, NPC and quest flags, abilities, the map, water levels, rescued Lost Lights |
| Reset when the room reloads or you rest at a beacon | Regular enemies, crumbling platforms, momentary switches, crates and pots, flares, lamps that are not protected |
| Never saved | Your position (you continue at a beacon), physics props in motion |

Rooms change with flags: flag gates add and remove entities, doors and tiles follow signals,
and the color grade follows the area's light %. NPCs have a place per story stage, chosen by
flags, so the hub fills up as you play.

## Meta and persistence

- 3 save slots: progress, flags, inventory, abilities, discovered map, per-entity world state,
  stats.
- Trials: two per area, entered through Trial doors in the world and from the menu once found.
  Time and score, bronze/silver/gold medals, results screen, best runs saved as ghosts. Gold on
  every Trial unlocks a skin.
- Journal: bestiary (kills and a light hint per enemy), Echoes, NPC notes.
- Stats: deaths, playtime, completion (the light % of the whole city). Achievements per area and
  for secrets.
- Cosmetics: palette-swap skins, lantern colors.

## Level design rules

- One idea per room. Rooms are 1 to 4 screens.
- Teach, test, twist: every mechanic appears first safely, then under pressure, then combined
  with another.
- Show the reward before the way to it. Locked things are visible before their key exists.
- Alternate tension and rest: no more than two dark rooms on the critical path without a light
  to refill at.
- A beacon every 4 to 6 rooms on the critical path, and one right before every boss.
- Every entrance has a PlayerStart nearby; every exit can be reached back, or the room says
  clearly that it is one way. The world validator checks both.
- Warm light marks the way on; cold light marks optional paths. Cracked walls show a hairline.
- Every room should give a reason to come back with a later ability.

## Customization and accessibility

Video (window mode, vsync, fps cap, effects toggles, shake intensity), audio sliders, full
rebinding (keyboard), colorblind filters, reduced flashing, text scale, assist mode (game speed,
invincibility, infinite dash, no flame drain), English and Swedish.

## Out of scope

Realtime multiplayer, procedural levels, machine learning. Possible post-1.0: online Trial
leaderboards with ghost sharing.
