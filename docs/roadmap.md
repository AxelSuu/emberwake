# Roadmap

| M | Name | Output |
|---|---|---|
| M0 | Foundation | Project, tooling, CI, docs, async fixed-step loop, scene stack, serde, storage, logging, headless tests, title screen, web build |
| M1 | Game feel | Input actions + rebinding model, player controller, tile collision, camera (deadzone, look-ahead, shake, hitstop), dev overlay F2/F3, one LDtk test room, placeholder art |
| M2 | World | ECS-lite, multi-room streaming, room transitions, parallax, LDtk entities, interactables + signals, beacons, save slots |
| M3 | Rendering | RenderFrame, GL backend (normal-mapped lighting, shadows, bloom, LUT, HD-2D DOF), particles, software parity |
| M4 | UI & meta | Widget toolkit with focus navigation, main menu, full settings, rebinding UI, pause, i18n, results, records |
| M5 | Combat & AI | Health and damage, frame hitboxes, 3 enemies, floating text, pymunk props, flares |
| M6 | Pipelines | Pixel DSL, atlas packer, normals, autotiles, palette lint, sfx generator (slice art moves to M10) |
| M7 | Boss tech | Skeletal rig + IK, cutscene coroutines (the boss itself moves to M9) |
| M8 | Depth | NPC dialogue and shop, Trials + ghosts, achievements, skins (map moves to M9, abilities to M11) |
| M9 | The Sunken Quarter | The first area playable start to boss in greybox: lantern swing, HUD, light rules v2, death and Cinder, abilities and flags, lamps and light switches, breakables, lifts, encounters, two enemies and an elite, three NPCs, map screen, 20 rooms, the Lamprey, story beats, art proof |
| M10 | The Quarter, finished | Art and audio for the slice: tilesets, back walls, decor, bitmap font, every sprite, GL backend with shaders (#23), music stems, sound effects, ambience |
| M11 | Brass Gardens | Area 2: Wickline and Shutter, shadeforms, vines and pollen, three enemies, Moth Queen, Bloomhusk, the Gardener, lenses, journal, fast travel |
| M12 | Tidal Works | Area 3: water level as world state, swimming with the Bell Jar, Ember glide and steam, four enemies, the Tidekeeper, Brine |
| M13 | Lantern Spire | Area 4 and the ending: mirrors and beams, light-bridge, shadow-step, three enemies, the Hollow Lamplighter, three endings, the Gloam (optional area) |
| M14 | Ship | PyInstaller builds, itch.io desktop + web demo, polish, performance pass, credits |

Detailed plans: [M2 World](plans/m2-world.md), [M9 The Sunken Quarter](plans/m9-sunken-quarter.md),
[art and audio](plans/art-audio.md). Areas: [the Sunken Quarter](world/sunken-quarter.md).

## M0 status

- [x] Project renamed to `emberwake` (was `pygame`, which shadowed the library)
- [x] uv, ruff, ty, import-linter, pytest + hypothesis, just, pre-commit
- [x] Core: event bus, fixed step, serde + versioned codec, logging
- [x] Platform: storage (file, memory, web), documents, display
- [x] Scene stack, async runner, debug overlay, boot and title scenes
- [x] Docs, ADRs
- [x] CI workflow
- [ ] Verify the pygbag build in a browser (#1)
- [ ] Spike: pymunk and numpy availability in pygbag (#2)
- [x] GitHub repo, labels, milestones, issues and project board

## M1 status

- [x] Player movement spec (#6)
- [x] Input actions, keyboard mapper, rebindable bindings in settings (#3; gamepad removed later, ADR 0018)
- [x] Run-length encoded replays, `--replay`, F9 to save (#4)
- [x] Tile grid and sub-stepped kinematic collision (#5)
- [x] Player controller: run, jump, coyote, buffer, apex hang, corner correction (#7)
- [x] Wall slide, wall jump, dash, one-way drop-through (#8)
- [x] `content/feel.toml` with F5 hot reload (#9)
- [x] Camera: deadzone, look-ahead, smoothing, bounds, interpolation (#10)
- [x] Juice: trauma shake, hitstop, squash and stretch (#11)
- [x] Typed LDtk loader (#12)
- [x] LDtk scaffold tool, schema-validated test room, traversal bots (#13)
- [x] Gameplay scene with placeholder art and lantern glow (#14)
- [x] Dev tools: F2 colliders, F3 free camera, P pause, `.` step, `,` slow motion (#15)
- [ ] Hands-on feel pass with a real keyboard

## M2 status

- [x] ECS-lite world with resources and phase schedule, player migrated (#16)
- [x] Level source: ASCII + TOML compiled to LDtk, Test_Room migrated (#64)
- [x] World coordinates, room graph, streaming, transitions (#17)
- [x] Prefabs and LDtk entity spawning, state persisted by iid (#19)
- [x] Interactables and signal wiring: levers, doors, plates, embers (#20)
- [x] Parallax backdrops: presets, blurred far layers, darkened near layers, cross-fades (#18)
- [x] Beacons and save slots: relight to save, continue, `--slot`, `--new` (#21)
- [x] Greybox world: five rooms around the test room (#65)

## M3 to M8 status

- [x] M3: RenderFrame, particles, post effects, soft shadows, light shafts (#22, #24 to #27).
  Open: GL backend (#23), moved to M10 for shaders on desktop; the browser keeps the software path.
- [x] M4: widgets, main menu, settings, rebinding, pause, strings in English and Swedish,
  results and records (#28 to #34). No pixel font yet (M10).
- [x] M5: combat basics, animation, three enemies, floating text, props and flares, light rules
  (#35 to #40). The player has no attack yet (M9).
- [x] M6: pixel DSL, atlas, normals, autotiles, palette lint, sfx, audio system (#41 to #46,
  #48). No art made with them yet; biome art (#47) moves to M10.
- [x] M7: rig and RotSprite, IK legs, cutscenes (#49, #50, #52). The Lamprey (#51) moves to M9.
- [x] M8: dialogue and shop, Trials and ghosts, achievements, cosmetics and assist (#54, #56 to
  #58). Map (#55) moves to M9; grapple and glide (#53) to M11 and M12.

## Beyond M9

Each area milestone follows the M9 shape: specs, systems, rooms in batches with bots, boss,
story beats, then its art and audio. The GDD has the design; each gets a plan in `plans/`.

**M10 The Quarter, finished.** Done when the Quarter has no placeholder art left, has music
stems that follow light and danger, a sound for every action, and ambience; text uses the bitmap
font. See the [art and audio plan](plans/art-audio.md).

**M11 Brass Gardens.** About 18 rooms. Wickline (rope physics on lamp hooks) and Shutter
(lantern off: stealth, shadeforms). Phototropic vines that grow toward the nearest light, pollen
pods that glow when struck. Mothling swarm, Thornspring, Shade; Moth Queen; Bloomhusk; the
Gardener's quest to light three sun lamps. Lenses (equipped at beacons), the journal (bestiary,
Echoes, notes), fast travel between lit beacons. Backtracking rewards open in the Quarter. Two
Trials.

**M12 Tidal Works.** About 18 rooms. Water level as world state: valves raise and lower water
across connected rooms, saved and drawn per room. Swimming with the Bell Jar (the lantern burns
underwater; flares do not). Ember glide over steam vents and braziers. Anglerlamp, Barnacle,
Tidecrab, Eelings; the Tidekeeper floods its arena in phases; Brine the diver. Two Trials.

**M13 Lantern Spire.** About 15 rooms plus the Gloam (8, optional). Mirrors and beams (ray casts
like the shadow code) routing beacon light to receivers, light-bridge, shadow-step. Mirror
Knight, Sentinel, Hollow Acolyte; the Hollow Lamplighter mirrors your abilities. The three
endings and credits. Two Trials, and Trials that span areas.

**M14 Ship.** Desktop builds (#59), itch.io (#60), performance (#61), polish and credits (#62),
the pymunk in pygbag spike (#2), a hands-on pass on every area.

Alongside every milestone:

- **A living world.** Critters that scatter from light (moths, rats, fish), NPC barks as speech
  bubbles, rain on the streets, swinging chains and signs, splashes, pots and bottles to break.
- **Accessibility.** Colorblind filters, text scale, and assist options for each new mechanic.
- **Meta.** Achievements, Trials and journal entries for each area.
