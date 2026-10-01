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
| `src/<room>.toml` | Optional: what each marker is, its fields and wiring, plus level fields |

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
one has no prefab or its fields do not fit.

| Entity | Meaning |
|---|---|
| PlayerStart | Spawn point; after a hazard death the one nearest the room's entrance (pivot: bottom centre) |
| Door | Solid while closed; opens while its sources are on (Mode any/all, Invert) |
| Lever | Interact to switch its targets (Mode toggle/momentary/once) |
| PressurePlate | On while something stands on it |
| Beacon | Interact to relight: saves, refills the dash and becomes the continue point |
| Ember | Collectible |
