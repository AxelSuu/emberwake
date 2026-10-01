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

## M0 status

- [x] Project renamed to `emberwake` (was `pygame`, which shadowed the library)
- [x] uv, ruff, ty, import-linter, pytest + hypothesis, just, pre-commit
- [x] Core: event bus, fixed step, serde + versioned codec, logging
- [x] Platform: storage (file, memory, web), documents, display
- [x] Scene stack, async runner, debug overlay, boot and title scenes
- [x] Docs, ADRs
- [x] CI workflow
- [ ] Verify the pygbag build in a browser (`just web-serve`)
- [ ] Spike: pymunk and numpy availability in pygbag
- [ ] GitHub repo, labels, milestones and issues (needs go-ahead)
