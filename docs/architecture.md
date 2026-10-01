# Architecture

## Layers

```
emberwake.app        wiring: builds services, pushes the first scene, runs the loop
emberwake.game       Emberwake content: scenes, components, systems, data models
emberwake.engine     reusable, game-agnostic
  core               pure Python: events, clock, serde, log, mathx, noise, jobs (later: fsm, tween)
  ecs                pure Python: entities, component stores, queries, resources, phase schedule
  platform           desktop vs browser: storage, documents, display
  scene              scene stack
  runner             the main loop
  input              per-tick action state, keyboard/gamepad mapper, replays
  physics            tile sources, sub-stepped kinematic collision
  render             camera, screen shake, chunked layers (later: backends, lighting, particles)
  world              LDtk loader, room graph, world grid, room streaming
  debug              fps overlay, time control (later: console, inspector window)
  (planned) assets, audio, ui
```

Runtime data lives outside the package: `content/` (TOML, e.g. `feel.toml`) and `levels/`
(LDtk, compiled from the ASCII + TOML in `levels/src` by `tools/levels`). `game/paths.py` finds
them; the web build copies both next to the package.

Dependencies point downward only. import-linter enforces it (`just check`).

## Main loop

`Runner.run` is async and yields once per frame so the browser build works. Each frame:

1. Poll events; global hotkeys (F11, F1) then the top scene's `handle`.
2. `FixedStep.advance(frame_time)` gives N steps; `SceneManager.update(1/60)` runs N times.
3. `SceneManager.draw(canvas, alpha)` with `alpha` for interpolation.
4. Present. `Display` uses `pygame.SCALED`, so the 640x360 canvas is upscaled on the GPU.

The simulation is deterministic: fixed dt and seeded `random.Random` per subsystem. That enables
input replays, Trial ghosts, bug repro files and headless scenario tests.

## Scenes

Stack with `push`, `pop`, `replace`, `switch`. Changes are queued and applied at the start of the
next update. Overlays set `blocks_update = False` / `blocks_draw = False` to keep the scene below
running or visible. Only the top scene gets input. Menus and settings are scenes, not OS windows;
extra OS windows (`pygame.Window`) are reserved for dev tools.

Planned flow: Boot -> Title -> MainMenu -> (Settings, SaveSelect, Trials, Credits) -> Gameplay
(+ Pause, Map, Inventory, Dialogue, Shop overlays) -> Results.

## World objects (M2)

ECS-lite (`engine.ecs`, [ADR 0012](adr/0012-ecs-deferred-changes-resources.md)): `World` holds
component stores (`dict[type, dict[EntityId, C]]`), typed queries for 1-4 component types and
resources (world singletons such as the tile grid, input and event bus). `spawn`, `add`, `remove`
and `despawn` are queued and applied by `flush`. A `Schedule` runs systems phase by phase and
flushes between phases; the gameplay phases (`game/schedule.py`) are `input -> logic -> physics
-> post -> camera -> render_prep`, with more (ai, combat, animation) added as systems need them.
Components are slotted dataclasses registered with `@component`, so prefabs and saves name them
as text and `serde` stores their data. UI widgets and scenes are plain OOP.

Prefabs ([ADR 0015](adr/0015-entity-state-by-iid.md)) live in `content/prefabs.toml`: components
with field values, a mapping from LDtk fields to component fields, and the components to persist.
When a room loads, `Spawner` spawns each LDtk entity as the prefab named after its identifier in
snake_case, adding `Identity` (iid, room, prefab) and a `Body` over its LDtk rect. Entity refs
stay iids and `Spawner.resolve` finds the live entity, if its room is loaded. When a room
unloads, persisted components are written to `WorldState` by iid and restored on the next spawn.
`tools.levels validate` (in `just check`) proves every placed entity has a prefab its fields fit.
Behavior: FSMs (player, simple enemies), behavior trees (bosses), generator coroutines
(cutscenes).

| Thing | Components |
|---|---|
| Player | Body, Motor (done); later Health, Animator, LightEmitter, Inventory, Abilities |
| Enemy | Body, Hurtbox, Hitbox, Health, Brain, Animator, LightSensitive, Loot |
| NPC | Transform, Animator, Interactable |
| Lever, door, plate | Interactable or Trigger, Switch, signal wiring via LDtk entity refs |
| Beacon | Interactable, LightEmitter, SavePoint, AreaGrade |
| Prop | Transform, PhysicsBody, Sprite |
| Pickup | Trigger, Pickup, Bob |

Mechanisms ([ADR 0016](adr/0016-doors-and-signals.md), `game/interact.py`, `game/signals.py`):
`Trigger` tracks player overlap, `Interactable` marks the nearest thing in reach and the
interact action uses it, `Switch` (toggle, momentary, once) lists receiver iids, a
`PressurePlate`'s switch follows its trigger, and a `Pickup` retires on touch. `Wiring` knows
every receiver's sources across the world, so `signal_system` powers `Receiver`s (any or all,
optionally inverted) in one pass in iid order, reading saved state for switches in unloaded
rooms. A `Door` sets its cells solid or empty in the `WorldGrid` and waits for the doorway to
clear before closing. F4 draws the wires, green when powered.

Systems talk through the `EventBus` (`EnemyKilled`, `PlayerHurt`, ...) so score, sfx, particles,
floating text and achievements stay decoupled.

## Input

Devices never reach gameplay. `InputMapper` turns key and gamepad events into a set of held
actions, sampled once per tick (taps shorter than a tick still count for one tick).
`InputState` derives `pressed`, `released` and buffered presses from consecutive frames. Because
gameplay sees only these frames, recording them (`ReplayRecorder`, run-length encoded) is enough
to replay a session exactly.

## Physics (M1 done, M5 planned)

Characters: custom kinematic AABBs, per-axis resolution against the LDtk IntGrid (solid,
one-way, hazard), sub-stepped to half a tile so nothing tunnels. The player controller
(`game/player/controller.py`) is a pure step function over a `Body` and a `Motor` that returns
events (`Jumped`, `Landed`, `Dashed`, `Died`); `player_system` runs it in the physics phase and
publishes the events on the bus, and feedback reacts. Entity overlap: spatial hash plus layer
bitmasks. Props, ropes, debris, flares: pymunk, with tile solids greedy-meshed into static boxes
and the player mirrored as a kinematic body.

## Rendering (planned, M3)

Gameplay emits a backend-agnostic `RenderFrame` (draw commands per layer, lights).

- GL backend (desktop, moderngl): albedo + normal + emissive buffers, deferred 2D lighting with
  normal maps and SDF soft shadows, bloom, LUT color grading, HD-2D depth of field, vignette,
  optional CRT.
- Software backend (browser, fallback): additive light gradients multiplied over the scene,
  baked glows, pre-blurred parallax layers.

Tiles are baked into 256x256 chunk surfaces; only visible chunks are drawn with `fblits`.

## World streaming (M2)

[ADR 0014](adr/0014-world-coordinates-streamed-rooms.md). The simulation runs in world pixels
(LDtk `worldX/worldY` of a GridVania world). `RoomGraph` holds every room's rect and computes
adjacency from shared edges. The active room is the one holding the player's centre;
`room_system` switches it, publishes `RoomEntered` and gives an upward boost when the player
comes up through a floor. `RoomStreamer` keeps the active room and its neighbours loaded and
unloads rooms two steps away (an `on_unload` hook runs first so their entities can be saved).
`WorldGrid` is the physics `TileSource`: it routes each cell to the loaded room owning it, empty
elsewhere, and the void below every room kills.

Each loaded room's art is a `ChunkLayer` of 256 px chunks. Its `bake` generator paints one chunk
per step and runs as a `Jobs` entry pumped for 2 ms per frame; drawing bakes any visible chunk
that is still missing. On a room change the camera glides into the new room's bounds with faster
smoothing, and the respawn point becomes that room's PlayerStart nearest to where the player
entered. F4 shows room rects, names and load state.

## Persistence

`Storage` (files in `pygame.system.get_pref_path` on desktop, `localStorage` in the browser) +
`VersionedCodec` (`{"version", "data"}` envelope, migration chain) + `load_document` /
`save_document` (JSON, atomic write, `.bak` generation, corrupt files kept as `.corrupt`).

Documents: `settings.json`, `slot_N.json`, `records.json`, `achievements.json`, `ghosts/*.rpl`.

## Performance rules

Convert every surface, never transform per frame, bake static layers, use `fblits`, pool
particles, slot dataclasses, spatial hashing. Budget: 8 ms per frame at 640x360 on a mid laptop.
