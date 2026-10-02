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
| PressurePlate | On while something stands on it |
| Beacon | Interact to relight: saves, refills the dash and becomes the continue point |
| Brazier | Cold until a swing or a flare lights it (`Lit` places it lit); then a light and an on switch, saved by iid. Its `Targets` are receivers |
| Photocell | On while the light at it reaches `Threshold` (default 0.4); `Targets` are receivers |
| Bell | A swing rings it: stuns enemies nearby and pulses its `Targets` for a moment |
| Lamp | Dead lamp post: a swing lights it, a Wisp-eater snuffs it. `Beacon` (a ref) is the beacon that makes it permanent once both are lit ([spec](../docs/specs/lamps.md)) |
| Ember | Collectible |
| CrackedWall | Solid until the lantern strikes it, then gone for good ([spec](../docs/specs/breakables.md)) |
| Crate | Solid; breaks for good when struck and flings `Embers` loose embers |
| Pot | Not solid; breaks like a crate |
| CrumblingPlatform | One-way; clears 0.5 s after the player lands on it and returns 2 s later |
| Hesper, Quill | NPCs ([spec](../docs/specs/npcs.md)); gate each spot with `Requires`/`Unless` on `hesper_stage` or `quill_stage`. `--room Npc_Lab` has every spot |
| Grant | Touch to receive an ability or item (`Thing`, a key of `content/grants.toml`, and `Count`) |
| FlagSwitch | Not drawn: powers its `Targets` while its `Condition` holds, also while its room is unloaded |
| SetFlag | Invisible zone: stepping in sets `Flag` to `Value`, or adds it with `Mode = "add"` |

## Level fields

Set in a room's TOML as `fields = { Name = value }`.

| Field | Default | Meaning |
|---|---|---|
| Backdrop | `cavern` | A preset in `content/backdrops.toml` |
| Area | `quarter` | A key of `content/areas.toml` (the dev rooms are `lab`). Entering another area shows its banner; its light % sets the grade's saturation ([spec](../docs/specs/areas.md)) |
| Music | empty | A stem set, a lowercase name; empty plays the area's `music`. Not played yet |
