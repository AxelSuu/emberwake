# Levels

`world.ldtk` is the LDtk project (https://ldtk.io, version 1.5.3+), compiled from `src/`
([ADR 0013](../docs/adr/0013-text-first-level-source.md)). Rebuild after editing the source:

    uv run python -m tools.levels build --merge

A test fails if the committed `world.ldtk` is out of date with `src/`.

Rooms made by hand in LDtk are kept by `--merge`: only levels with `Generated = true` are
rebuilt. Do not edit generated levels in LDtk; the next build overwrites them.

## Source

| File | Contents |
|---|---|
| `src/defs.toml` | Entity types (size, pivot, fields) and level fields |
| `src/world.toml` | Each room's top-left cell on the GridVania grid (20x11 tiles, 320x176 px) |
| `src/<room>.txt` | The room's tiles, one character per 16 px tile; size in whole grid cells |
| `src/<room>.toml` | Optional: what each marker is, its fields and wiring, plus level fields such as `Backdrop` (a preset in `content/backdrops.toml`, default `cavern`) |

Real rooms start at cell x 0 with `Wake` at [0, 0]. The dev rooms (area `lab`) live at x 60 and
up so they never touch the real map: the greybox cluster takes x 60 to 69, y 0 to 9; put new lab
rooms at x 70 and up (or further down at x 60), each clear of every other room, and set
`Area = "lab"`.

Rooms connect where their edges touch and the tiles there are open. Put a PlayerStart near each
entrance: it is where the player respawns after a hazard death.

Tiles: `#` solid, `=` one-way, `^` hazard, `.` empty. Letters and digits are entity markers on
empty tiles. Each 4-connected rectangle of one marker is one entity of that size; `P` is a
PlayerStart without any TOML.

```toml
# src/lever_hall.toml
[entities.a]
type = "Lever"
fields = { Targets = ["b"] }   # entity refs name a marker, or "Other_Room:b"
[entities.b]
type = "Door"                  # drawn as a 1x3 block of b in the .txt
```

A marker used for several blocks (embers, say) cannot be the target of a ref. Entity iids come
from the room name and marker, so moving an entity keeps its saved state.

## Collisions layer (IntGrid)

| Value | Name | Meaning |
|---|---|---|
| 1 | Solid | Blocks from every side |
| 2 | OneWay | Blocks only from above; down + jump drops through |
| 3 | Hazard | Kills on touch |

## Entities

See `src/defs.toml` for fields. Each entity spawns the prefab named after it in snake_case from
`content/prefabs.toml`; `uv run python -m tools.levels validate` (part of `just check`) fails if
one has no prefab or its fields do not fit. It also checks the world as a whole: wiring targets
exist, flags are set somewhere, every entrance has a PlayerStart within 6 tiles, and every room
but the `lab` and trial rooms is reachable from the start room with the abilities found by then
([spec](../docs/specs/world-validator.md)).

Every entity also takes `Requires` and `Unless`, conditions in the dialogue syntax over the save's
flags, with `has.<thing>` for abilities and item counts (`Requires = "met_tinker"`, `Unless =
"has.shard>=3"`). It is in the world only while `Requires` holds and `Unless` does not, and comes
and goes live as they change ([spec](../docs/specs/world-flags.md)).

| Entity | Meaning |
|---|---|
| PlayerStart | Spawn point; after a hazard death the one nearest the room's entrance (pivot: bottom centre) |
| Door | Solid while closed; opens while its sources are on (Mode any/all, Invert) |
| Lever | Interact to switch its targets (Mode toggle/momentary/once) |
| PressurePlate | On while the player stands on it or a PushCrate rests on it |
| Beacon | Interact to relight: saves, refills the dash and becomes the continue point |
| Brazier | Cold until a swing or a flare lights it (`Lit` places it lit); then a light and an on switch, saved by iid. Its `Targets` are receivers |
| Photocell | On while the light at it reaches `Threshold` (default 0.4); `Targets` are receivers. `Sealed` keeps it dark until the Lamprey breaks its casing |
| Bell | A swing rings it: stuns enemies nearby and pulses its `Targets` for a moment |
| Lamp | Dead lamp post: a swing lights it, a Wisp-eater snuffs it. `Beacon` (a ref) is the beacon that makes it permanent once both are lit ([spec](../docs/specs/lamps.md)) |
| Lamprey | Boss ([spec](../docs/specs/lamprey.md)): its head at the water line of its arena, which is the room. `--room Cistern_Lab` has the arena: lamps, sealed photocells and a drain door on a FlagSwitch for `lamprey_drained` |
| Ember | Collectible |
| CrackedWall | Solid until the lantern strikes it, then gone for good ([spec](../docs/specs/breakables.md)) |
| PushCrate | A box the player pushes by walking into it; falls, stacks, can be stood on and weighs plates; saved by iid, home again after a beacon rest ([spec](../docs/specs/push-crates.md)) |
| Platform | A solid box (default 3x1 tiles) that carries riders along its `Path`, the `PathNode` refs it visits after its home, in the same room. Wired (`Mode`, `Invert`) it is a lift: it goes to the last node while powered and back while not; unwired it loops, resting at each end. `Speed` overrides px/s. Never crushes: it holds still while something is in the way ([spec](../docs/specs/lifts.md)). `--room Lift_Lab` has a lever lift, a loop over spikes and a two-node lift |
| PathNode | A stop on a Platform's `Path`: the platform's top-left corner goes here. Not drawn, not solid |
| Crate | Solid; breaks for good when struck and flings `Embers` loose embers |
| Pot | Not solid; breaks like a crate |
| CrumblingPlatform | One-way; clears 0.5 s after the player lands on it and returns 2 s later |
| Hesper, Quill | NPCs ([spec](../docs/specs/npcs.md)); gate each spot with `Requires`/`Unless` on `hesper_stage` or `quill_stage`. `--room Npc_Lab` has every spot |
| Encounter | Arena zone: the player's body in it shuts its `Doors` (open unless it runs; `Mode` and `Invert` are ignored) and starts the waves; clearing it powers its `Targets`, for good ([spec](../docs/specs/encounters.md)) |
| WaveSpawn | Where an enemy of `Kind` (an enemy prefab) appears in `Wave` (from 1, no gaps) of the `Encounter` (a ref, same room). Markers cannot sit inside a zone, so leave a row free |
| Grant | Touch to receive an ability or item (`Thing`, a key of `content/grants.toml`, and `Count`) |
| FlagSwitch | Not drawn: powers its `Targets` while its `Condition` holds, also while its room is unloaded |
| SetFlag | Invisible zone: stepping in sets `Flag` to `Value`, or adds it with `Mode = "add"` |
| Signpost | Shows the string `sign.<Text>` while the player is near, `{jump}` and so on as the current keys |
| Echo | Interact to replay `content/echoes/<Id>.json` as a ghost, with the string `echo.<Id>`; counts toward light % |
| LostLight | Follows the player to a beacon and is rescued there: sets `lost_light_<Id>` and adds to `lost_lights` |
| TrialDoor | Interact to unlock the Trial `Trial` in the menu and start it |

## Level fields

Set in a room's TOML as `fields = { Name = value }`.

| Field | Default | Meaning |
|---|---|---|
| Backdrop | `cavern` | A preset in `content/backdrops.toml` |
| Area | `quarter` | A key of `content/areas.toml` (the dev rooms are `lab`). Entering another area shows its banner; its light % sets the grade's saturation ([spec](../docs/specs/areas.md)) |
| Music | empty | A stem set, a lowercase name; empty plays the area's `music`. Not played yet |
