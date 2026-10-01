# M2 plan: World

**Goal.** Turn the single test room into a small connected greybox world with things to
interact with and progress that persists. M2 is done when you can:

1. Walk between 5 or more rooms with seamless camera transitions, backed by parallax backdrops.
2. Pull a lever to open a door, hold a door open with a pressure plate, collect embers.
3. Relight a beacon, quit, start the game again and continue from that beacon, with levers,
   doors, embers and beacons as you left them.

Everything is still placeholder art; real art is M6, menus are M4.

## Decisions

Decided here (each becomes an ADR when its PR lands):

| # | Decision | Why |
|---|---|---|
| D1 | Simulation moves to **world coordinates** (LDtk `worldX/worldY`). Rooms keep their own grids; a `WorldGrid` routes tile queries to whichever loaded room owns the cell. | Seamless transitions, no coordinate remapping at room edges. |
| D2 | **ECS-lite in `engine.ecs`** with resources (world singletons) and a phase schedule. The player controller stays a pure function; a system wraps it. | ADR 0006; keeps the tested M1 code intact. |
| D3 | **Hazard deaths respawn at the room entry point** (Celeste); beacons are save/continue points (and, from M5, where combat deaths return you). | Fast retries on platforming, meaningful save points. |
| D4 | **Persistent world state is keyed by LDtk `iid`** and snapshotted when a room unloads or the game saves. | Stable across edits; unloaded rooms need no live entities. |
| D5 | **Doors change collision tiles**; their visuals are sprites, so no chunk re-bake is needed. | Simple, and physics stays tile-only. |
| D6 | **A replay covers one session from a known start** (room plus slot state). Loading or saving mid-replay is out of scope. | Keeps replays simple until Trials (M8). |

Needs your call (default in bold; work proceeds on the default unless you say otherwise):

| # | Question | Options |
|---|---|---|
| Q1 | Level source of truth while Claude builds most rooms | **Text-first: ASCII + TOML sidecars compiled into `world.ldtk`; rooms you create or edit in LDtk are kept by a merge** / LDtk-only from now on (you build rooms in LDtk) |
| Q2 | Interact button | **Up (plus E on keyboard, Y on gamepad)** / a dedicated button only |
| Q3 | Who merges PRs | **You merge; Claude opens them and keeps CI green** / Claude merges once CI is green |

## Work breakdown and order

```
 #16 ECS-lite ──┬─► #17 Rooms & streaming ──┬─► #18 Parallax
                │                            │
 #64 Level      ├─► #19 Prefabs & spawning ──┴─► #20 Interactables ──► #21 Beacons & saves
     source ────┘                                                         │
                                         #65 Greybox world ◄──────────────┘ (grows with each PR)
```

One PR per box, branch `m2/<issue>-<slug>`, PR body `Closes #N`. PRs that depend on an unmerged
one are stacked (based on its branch); GitHub retargets them to `main` when the base merges.

| PR | Issue | Size (est.) | Depends on |
|---|---|---|---|
| A | #16 ECS-lite, player migrated | ~500 lines | M1 |
| B | #64 Level source: layout, entities, wiring, merge | ~500 | M1 |
| C | #17 World coordinates, room graph, streaming, transitions | ~700 | A |
| D | #19 Prefab registry, TOML prefabs, LDtk spawning, persistence hooks | ~500 | A, B |
| E | #20 Triggers, interact, switches, signals, doors, plates, wire overlay | ~600 | C, D |
| F | #18 Parallax backdrops with cross-fade | ~350 | C |
| G | #21 Beacons, save slots, continue, world state | ~600 | C, E |
| H | #65 Greybox world: 5+ rooms | grows in B-G | B |

## Design per issue

### #16 ECS-lite world

`engine/ecs/` (pure Python, no pygame):

```python
world = World()
player = world.spawn(Body(...), Motor(), Facing(1))  # returns EntityId immediately
world.add(player, Visual())  # structural changes are deferred
for eid, body, motor in world.query(Body, Motor):
    ...  # typed overloads for 1-4 types
world.resource(Camera)  # singletons: grid, camera, input, bus
schedule = Schedule(["input", "logic", "physics", "post", "camera", "render_prep"])
schedule.add("physics", player_system)
schedule.run(world, dt)  # flushes spawns/despawns between phases
```

- Stores: `dict[type, dict[EntityId, component]]`; queries iterate the smallest store.
- Spawns and despawns are queued and applied at phase boundaries, so systems never mutate a store
  they are iterating.
- `@component` registers a class by name for prefabs and saves (serde handles the data).
- Player migration: `Player` splits into `Body` (engine physics) + `Motor` (the controller state).
  `step()` takes both; its 24 scenario tests keep passing unchanged in spirit.
- Benchmark: 1,000 entities, a 2-component query in under 0.3 ms (pytest-benchmark, non-blocking).

### #64 Level source (new)

Extends `tools/ldtk_scaffold.py` into `tools/levels/` (Q1 default):

```
levels/src/world.toml        room placement on the GridVania grid (320x176 cells)
levels/src/<room>.txt        ASCII tiles; letters/digits are entity markers
levels/src/<room>.toml       what each marker is, with fields and wiring
```

```toml
# levels/src/lever_hall.toml
[entities.a]
type = "Lever"
fields = { Targets = ["b"] }     # marker refs become LDtk EntityRef fields
[entities.b]
type = "Door"
size = [1, 3]                    # in tiles
```

- Generates entity definitions and field definitions (Bool, Int, String, EntityRef arrays) for
  Door, Lever, PressurePlate, Beacon, Ember, PlayerStart.
- Generated levels carry a level field `Generated = true`; `--merge` regenerates those and keeps
  every other level, so rooms built by hand in LDtk survive.
- Output stays schema-valid (existing test) and loads through `engine.world.ldtk`.

### #17 Rooms, streaming and transitions

- `RoomGraph` from the LDtk project: room rects in world space, adjacency computed from rects.
- `Room` (runtime): grid with world origin, baked chunks (256 px), entity spawns, bounds.
- `WorldGrid` implements the tile-source protocol for physics; cells outside loaded rooms are
  empty, and falling out of every room is death.
- Active room = room containing the player's centre. On change: `RoomEntered(room, entry_point)`;
  camera bounds switch and the camera glides (faster smoothing during the glide);
  neighbours load; rooms two steps away unload after their entities are snapshotted (D4).
- Baking is a generator that bakes one chunk per step, pumped with a per-frame budget, so loading
  a neighbour never spikes a frame (assert in a test: no single pump step bakes more than one chunk).
- Entering a room from below gives a small upward boost so players are not dropped back out.
- Respawn after a hazard death is the active room's entry point (D3).
- F4 dev overlay: room rects, ids and load state.

### #18 Parallax and depth

- Level field `Backdrop` names a preset in `content/backdrops.toml`; each layer has a depth factor,
  a placeholder generator (skyline, pillars, mist bands) and palette colours.
- Far layers are pre-blurred once with `transform.gaussian_blur` (cheap HD-2D depth on the
  software path); foreground occluders (factor > 1) are darkened.
- Layers wrap horizontally; vertical offset is clamped.
- Changing backdrop between rooms cross-fades over 0.5 s.

### #19 Prefabs and spawning

```toml
# content/prefabs.toml
[lever]
components = { Sprite = { image = "lever" }, Interactable = { prompt = "pull" }, Switch = {} }
fields = { Targets = "Switch.targets", Mode = "Switch.mode" }   # LDtk field -> component field
persist = ["Switch"]                                             # saved per iid
```

- LDtk entity identifier maps to a prefab (`Lever` → `lever`); unknown identifiers log a warning
  and spawn nothing.
- Entity refs are stored as iids and resolved lazily, so refs into unloaded rooms work.
- `tools/levels validate`: every LDtk entity has a prefab and every mapped field exists, in CI.

### #20 Interactables and signals

| Component | Behaviour |
|---|---|
| `Trigger` | rect; emits `Entered` / `Exited` when the player body overlaps |
| `Interactable` | in range + `INTERACT` pressed → `Interacted`; draws a prompt glyph |
| `Switch` | `toggle`, `momentary` or `once`; changes emit `SwitchChanged` |
| `Receiver` | powered when `any` / `all` of its sources are on, optional `invert` |
| `Door` | sets its tiles solid when closed, empty when open; closing waits while the player is inside |
| `PressurePlate` | momentary switch driven by a trigger |
| `Pickup` | collected on enter, persisted, emits `Collected` |

- New action `INTERACT` (Q2 default bindings: up, W, E / Y, d-pad up).
- Signal propagation is one pass per tick in iid order, so results are deterministic.
- Dev overlay draws wires from switches to receivers, green when powered.

### #21 Beacons and save slots

```python
@dataclass
class SaveSlot:
    room: str  # last beacon's room
    beacon: str  # its iid
    playtime: float
    flags: dict[str, int]
    entities: dict[str, dict[str, Any]]  # iid -> persisted component data
    discovered: list[str]  # room iids
    stats: Stats  # deaths, jumps, dashes, embers
```

- `saves/slot_{1,2,3}.json` through `Storage` + `VersionedCodec` (atomic, backed up).
- Relighting a beacon: save, refill dash, set the continue point, flash + shake + particle burst
  placeholder, and the room's backdrop shifts warm (a preview of the M3 colour grade).
- Start-up: `--slot N` (default 1) continues from the slot's beacon; `--new` starts fresh. Menus
  replace these flags in M4.
- Playtime and stats tracked; saving also happens on quit (position is not saved, only progress).
- Tests: save → load round trip restores every persisted entity; migration test template for v2.

### #65 Greybox world (new)

Five or more rooms forming a loop around the existing Test_Room: an entry hall with the first
beacon, a lever-and-door hall, a vertical shaft going up, a pressure-plate room with a timed door,
and an upper room with the second beacon and embers. Every room gets a traversal bot test like the
M1 ones, so tuning changes can never make the world impossible.

## Verification for the milestone

- `just check`, `just test` green; new bot tests walk the full loop and use every interactable.
- `just run --dev`: the three goal scenarios above, by hand.
- `just web`: the browser build saves and continues through `localStorage` (also closes #1).
- Frame budget: F1 graph stays under 8 ms while crossing room boundaries.

## Risks

- **World-coordinate refactor** touches physics, camera and tests. Mitigation: land it alone in
  PR C with the M1 bots as a safety net.
- **Python ECS overhead.** Mitigation: tile collision stays outside the ECS; benchmark in PR A.
- **Text and LDtk drifting apart** if both are edited. Mitigation: `Generated` flag + merge (Q1).
