# 0013 Text-first level source compiled to LDtk

Refines [0005](0005-ldtk-levels.md). Plan question Q1 in `docs/plans/m2-world.md`.

**Context.** Most rooms are built by an agent that cannot drive the LDtk editor, and reviewing
LDtk JSON diffs is hard. People still want to build or polish rooms in LDtk.

**Decision.** Rooms live in `levels/src` as ASCII maps plus TOML (markers, fields, entity-ref
wiring), with room placement in `world.toml` and entity types in `defs.toml`.
`tools/levels build` compiles them into `levels/world.ldtk`, which the game keeps loading as
before. Generated levels carry `Generated = true`; `--merge` rebuilds only those and keeps every
other level and every definition `defs.toml` does not list, reusing existing uids. Iids are
derived from names (room, marker), so they stay stable across rebuilds and edits.

**Consequences.** Room diffs are readable text, and a test keeps `world.ldtk` in sync with the
source. A room is either generated or hand-made, never both: edits to a generated level in LDtk
are lost on the next build. To move a room to LDtk, clear its `Generated` flag there, then drop
it from `world.toml`. Room sizes and positions are whole GridVania cells.
