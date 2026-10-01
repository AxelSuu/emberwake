# Game design document

Living document. Mechanics get their own spec in `specs/` before implementation.

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

## Core loop

Explore dark room -> fight/solve with light -> find beacon -> relight (save, heal, area regains
color) -> unlock ability or path -> new region.

## Player verbs

| Verb | Notes |
|---|---|
| Run, jump | Coyote time, jump buffer, variable height, corner correction, apex hang |
| Wall slide / wall jump | |
| Ember dash | 8-direction, refills on ground or beacon light |
| Lantern swing | Melee, knockback, ignites braziers |
| Throw flare | Physics object (pymunk) and temporary light source |
| Unlocks | Grapple (rope), glide, light-bridge, shadow-step |

## Light rules

- Ember (HP-like) drains slowly in total darkness and refills near light.
- Shadow creatures take damage over time in light and flee strong light.
- Lightforms: platforms that only exist while lit.
- Beacons: checkpoints and saves; relighting shifts the area's color grade.

## Content (vertical slice)

- Biome 1, The Sunken Quarter: ~15 rooms, 3 enemy types (Wisp-eater, Clockrat, Gloomcrawler),
  2 abilities (dash, flare), 1 skeletal boss (The Lamprey), 2 Trials, 1 NPC (the Tinker, shop).

Later biomes: Brass Gardens, Tidal Works, The Lantern Spire.

## Meta and persistence

- 3 save slots: progress, flags, inventory, abilities, discovered map, per-entity world state, stats.
- Trials: time and score, bronze/silver/gold medals, results screen, best runs saved as ghosts.
- Stats: deaths, playtime, completion %. Achievements.
- Cosmetics: palette-swap skins, lantern colors.

## Customization and accessibility

Video (window mode, vsync, fps cap, effects toggles, shake intensity), audio sliders, full
rebinding (keyboard + gamepad), colorblind filters, reduced flashing, text scale, assist mode
(game speed, invincibility, infinite dash), English and Swedish.

## Out of scope

Realtime multiplayer, procedural levels, machine learning. Possible post-1.0: online Trial
leaderboards with ghost sharing.
