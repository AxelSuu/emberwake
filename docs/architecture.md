# Architecture

## Layers

```
emberwake.app        wiring: builds services, pushes the first scene, runs the loop
emberwake.game       Emberwake content: scenes, components, systems, data models
emberwake.engine     reusable, game-agnostic
  core               pure Python: events, clock, serde, log, mathx, noise (later: ecs, fsm, tween)
  platform           desktop vs browser: storage, documents, display
  scene              scene stack
  runner             the main loop
  input              per-tick action state, keyboard/gamepad mapper, replays
  physics            tile grid, sub-stepped kinematic collision
  render             camera, screen shake (later: backends, lighting, particles)
  world              LDtk loader (later: rooms, streaming)
  debug              fps overlay, time control (later: console, inspector window)
  (planned) assets, audio, ui
```

Runtime data lives outside the package: `content/` (TOML, e.g. `feel.toml`) and `levels/`
(LDtk). `game/paths.py` finds them; the web build copies both next to the package.

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

## World objects (planned, M1-M2)

ECS-lite: `World` holds component stores (`dict[type, dict[EntityId, C]]`), typed queries and a
phase schedule `input -> ai -> pre_physics -> physics -> post_physics -> combat -> animation ->
camera -> render_prep`. Components are slotted dataclasses, so they serialize with `serde`.
Prefabs are TOML; LDtk entities spawn prefabs and their `iid` is the stable identity for
persistent world state. UI widgets and scenes are plain OOP. Behavior: FSMs (player, simple
enemies), behavior trees (bosses), generator coroutines (cutscenes).

| Thing | Components |
|---|---|
| Player | Transform, KinematicBody, Collider, PlayerController, Health, Animator, LightEmitter, Inventory, Abilities, CameraTarget |
| Enemy | Transform, KinematicBody, Collider, Hurtbox, Hitbox, Health, Brain, Animator, LightSensitive, Loot |
| NPC | Transform, Animator, Interactable |
| Lever, door, plate | Interactable or Trigger, Switch, signal wiring via LDtk entity refs |
| Beacon | Interactable, LightEmitter, SavePoint, AreaGrade |
| Prop | Transform, PhysicsBody, Sprite |
| Pickup | Trigger, Pickup, Bob |

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
(`game/player/controller.py`) is a pure step function that returns events (`Jumped`, `Landed`,
`Dashed`, `Died`); the gameplay scene publishes them on the bus and feedback reacts. Entity overlap: spatial hash plus layer bitmasks. Props, ropes,
debris, flares: pymunk, with tile solids greedy-meshed into static boxes and the player mirrored
as a kinematic body.

## Rendering (planned, M3)

Gameplay emits a backend-agnostic `RenderFrame` (draw commands per layer, lights).

- GL backend (desktop, moderngl): albedo + normal + emissive buffers, deferred 2D lighting with
  normal maps and SDF soft shadows, bloom, LUT color grading, HD-2D depth of field, vignette,
  optional CRT.
- Software backend (browser, fallback): additive light gradients multiplied over the scene,
  baked glows, pre-blurred parallax layers.

Tiles are baked into 256x256 chunk surfaces; only visible chunks are drawn with `fblits`.

## World streaming (planned, M2)

LDtk GridVania world, one level per room in its own file. Current and neighbouring rooms stay
loaded; neighbours bake one chunk per frame through a generator. The camera is clamped to room
bounds and glides across on transitions.

## Persistence

`Storage` (files in `pygame.system.get_pref_path` on desktop, `localStorage` in the browser) +
`VersionedCodec` (`{"version", "data"}` envelope, migration chain) + `load_document` /
`save_document` (JSON, atomic write, `.bak` generation, corrupt files kept as `.corrupt`).

Documents: `settings.json`, `slot_N.json`, `records.json`, `achievements.json`, `ghosts/*.rpl`.

## Performance rules

Convert every surface, never transform per frame, bake static layers, use `fblits`, pool
particles, slot dataclasses, spatial hashing. Budget: 8 ms per frame at 640x360 on a mid laptop.
