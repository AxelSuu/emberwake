# Roadmap

| M | Name | Output |
|---|---|---|
| M0 | Foundation | Project, tooling, CI, docs, async fixed-step loop, scene stack, serde, storage, logging, headless tests, title screen, web build |
| M1 | Game feel | Input actions + rebinding model, player controller, tile collision, camera (deadzone, look-ahead, shake, hitstop), dev overlay F2/F3, one LDtk test room, placeholder art |
| M2 | World | ECS-lite, multi-room streaming, room transitions, parallax, LDtk entities, interactables + signals, beacons, save slots |
| M3 | Rendering | RenderFrame, GL backend (normal-mapped lighting, shadows, bloom, LUT, HD-2D DOF), particles, software parity |
| M4 | UI & meta | Widget toolkit with focus navigation, main menu, full settings, rebinding UI, pause, i18n, results, records |
| M5 | Combat & AI | Health and damage, frame hitboxes, 3 enemies, floating text, pymunk props, flares |
| M6 | Pipelines + slice art | Pixel DSL, atlas packer, normals, autotiles, palette lint, sfx generator, biome 1 art and audio |
| M7 | Boss | Skeletal rig + IK, behavior tree, cutscene coroutines |
| M8 | Depth | More abilities, NPC dialogue and shop, map screen, Trials + ghosts, achievements, skins |
| M9 | Ship | PyInstaller builds, itch.io desktop + web demo, polish, performance pass |

Detailed plans: [M2 World](plans/m2-world.md).

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
- [x] Input actions, keyboard/gamepad mapper, rebindable bindings in settings (#3)
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
- [ ] Hands-on feel pass with a real keyboard and gamepad

## M2 status

- [x] ECS-lite world with resources and phase schedule, player migrated (#16)
- [ ] Level source: ASCII + TOML compiled to LDtk (#64)
- [ ] World coordinates, room graph, streaming, transitions (#17)
- [ ] Prefabs and LDtk entity spawning (#19)
- [ ] Interactables and signal wiring (#20)
- [ ] Parallax and depth layers (#18)
- [ ] Beacons and save slots (#21)
- [ ] Greybox world: five rooms around the test room (#65)
