# 0012 ECS details: deferred structural changes, resources, phase schedule

Refines [0006](0006-ecs-lite-oop-ui.md). Plan decision D2 in `docs/plans/m2-world.md`.

**Context.** Systems iterate component stores while spawning, despawning and attaching
components (pickups vanish, doors open, prefabs spawn). Mutating a dict while iterating it fails,
and changes that apply mid-tick make results depend on system order in subtle ways. Systems also
need shared singletons (tile grid, input, event bus, tuning) without global state.

**Decision.** `engine.ecs` is pure Python with no pygame (import-linter enforces it).
`spawn` returns an id at once, but `spawn`, `add`, `remove` and `despawn` are queued and applied
in order by `World.flush`; `Schedule.run` flushes before the first phase and after each one.
Singletons are resources keyed by type. Phases are named by the game, not the engine. Components
register by class name with `@component` so prefabs and saves can name them. Queries iterate the
smallest store; tile collision stays outside the ECS. The player controller stays a pure function
over `Body` and `Motor`, and a system wraps it.

**Consequences.** A component added in one phase is visible from the next phase on, never later
in the same one. Code outside a schedule (scene setup, tests) calls `flush` itself. Query order
is insertion order of the smallest store, so it is deterministic but not sorted; systems that
need a fixed order (signals) sort explicitly. A 2-component query over 1,000 entities takes
about 0.1 ms (`just bench` checks a 0.3 ms budget).
