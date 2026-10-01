# 0016 Doors change collision tiles; signals settle in one ordered pass

Plan decision D5 in `docs/plans/m2-world.md`.

**Context.** Levers and plates drive doors, possibly across rooms. Doors must block the player
exactly like walls, and the result must not depend on system or dict order, or replays break.

**Decision.** A door owns the cells under its body: closed, they are solid tiles in the
`WorldGrid`; open, empty. Its look is a sprite, so no chunk is re-baked. Switches name receivers
by iid; a world-wide `Wiring` index lists each receiver's sources, and `signal_system` evaluates
receivers once per tick in iid order. A source in an unloaded room counts from its saved state.

**Consequences.** Physics stays tile-only and doors need no special collision code. Receivers
cannot drive other switches, so one pass is always enough; chains would need a fixed-point loop.
Door cells are rewritten every tick, which also restores them after a room reloads.
