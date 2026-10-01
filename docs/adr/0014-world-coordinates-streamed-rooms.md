# 0014 World coordinates, streamed rooms, respawn at the room entrance

Plan decisions D1 and D3 in `docs/plans/m2-world.md`.

**Context.** M1 simulated one room in its own coordinates. A connected world needs seamless
movement across room edges, memory and frame time that do not grow with the world, and fast
retries after a platforming death.

**Decision.** Everything simulates in world pixels. Rooms keep their own tile grids; a
`WorldGrid` routes tile queries to the loaded room that owns the cell, and physics depends only
on the `TileSource` protocol (`tile_size`, `get`, `void`). The active room and its neighbours are
loaded; rooms two steps away are unloaded after an `on_unload` hook. Room art is baked in 256 px
chunks by generators under a per-frame time budget. A hazard death respawns the player at the
active room's PlayerStart nearest to where they entered (Celeste); beacons (#21) are save and
continue points.

**Consequences.** No coordinate remapping at room edges, and the camera simply glides into new
bounds. Rooms must be aligned to the tile grid (GridVania guarantees it). Moving rapidly back and
forth across an edge can unload and re-bake a room. Rooms need a PlayerStart near each entrance,
or the player respawns where they entered.
