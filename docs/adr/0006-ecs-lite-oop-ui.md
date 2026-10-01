# 0006 ECS-lite for world objects, OOP for UI and scenes

**Context.** Deep inheritance trees for game objects get rigid; full ECS frameworks are verbose
and fight Python's strengths.

**Decision.** An in-house ECS-lite (component stores keyed by type, typed queries, phase
schedule) for everything in the world. Components are slotted dataclasses, so the same serde
saves them. Scenes and UI widgets stay plain classes. Behavior uses FSMs, behavior trees for
bosses and generator coroutines for cutscenes.

**Consequences.** Prefabs are pure data (TOML) and LDtk entities map onto them. Systems are easy
to test in isolation. We maintain ~300 lines of ECS code instead of a dependency.
