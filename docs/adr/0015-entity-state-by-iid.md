# 0015 Prefabs from TOML, entity state keyed by LDtk iid

Plan decision D4 in `docs/plans/m2-world.md`.

**Context.** Rooms stream in and out, so their entities are created and destroyed many times. A
lever pulled or an ember collected must stay that way, in unloaded rooms and across saves, and
entities wired to each other may sit in different rooms.

**Decision.** Entity types are TOML prefabs naming registered components, with LDtk fields mapped
onto component fields. An entity's LDtk iid is its identity: references between entities are
iids, resolved to live entities on demand, and a prefab's `persist` components are written to a
`WorldState` keyed by iid when the room unloads or the game saves, then restored on spawn.
Unloaded rooms keep no live entities.

**Consequences.** Saves contain only the state that changed, keyed by ids that survive level
edits (generated iids derive from room and marker names, ADR 0013). Systems must handle a ref
whose target is not loaded. Deleting an entity in LDtk orphans its saved state, which is ignored.
A CI check keeps prefabs and LDtk fields in step.
