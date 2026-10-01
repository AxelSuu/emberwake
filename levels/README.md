# Levels

`world.ldtk` is the LDtk project (https://ldtk.io, version 1.5.3+). Edit it in LDtk.

`ascii/` holds the ASCII maps it was bootstrapped from with `tools/ldtk_scaffold.py`. They are
not kept in sync; once a room is edited in LDtk, the LDtk file is the source of truth.

## Collisions layer (IntGrid)

| Value | Name | Meaning |
|---|---|---|
| 1 | Solid | Blocks from every side |
| 2 | OneWay | Blocks only from above; down + jump drops through |
| 3 | Hazard | Kills on touch |

## Entities

| Entity | Meaning |
|---|---|
| PlayerStart | Spawn and respawn point (pivot: bottom centre) |
