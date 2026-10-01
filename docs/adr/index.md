# Architecture decision records

Short records of decisions that shape the project. Format: Context, Decision, Consequences.
Superseded records stay, marked as such.

| # | Decision |
|---|---|
| [0001](0001-light-driven-action-platformer.md) | Genre: light-driven action-platformer |
| [0002](0002-pygame-ce-python-312-pygbag.md) | pygame-ce, Python 3.12 syntax floor, pygbag as secondary target |
| [0003](0003-fixed-step-async-loop.md) | Deterministic fixed-step simulation in an async loop |
| [0004](0004-own-serde-not-pydantic.md) | Own serde instead of pydantic at runtime |
| [0005](0005-ldtk-levels.md) | LDtk for levels |
| [0006](0006-ecs-lite-oop-ui.md) | ECS-lite for world objects, OOP for UI and scenes |
| [0007](0007-hybrid-physics.md) | Hybrid physics: kinematic characters, pymunk props |
| [0008](0008-dual-render-backends.md) | GL and software render backends |
| [0009](0009-persistence.md) | Storage abstraction, versioned JSON, atomic writes |
| [0010](0010-art-pipeline.md) | Art pipeline: Resurrect 64, 16 px, pixel DSL, generated normals |
| [0011](0011-process.md) | Process: specs, ADRs, GitHub issues, CI gates |
| [0012](0012-ecs-deferred-changes-resources.md) | ECS details: deferred structural changes, resources, phase schedule |
| [0013](0013-text-first-level-source.md) | Text-first level source compiled to LDtk |
| [0014](0014-world-coordinates-streamed-rooms.md) | World coordinates, streamed rooms, respawn at the room entrance |
| [0015](0015-entity-state-by-iid.md) | Prefabs from TOML, entity state keyed by LDtk iid |
| [0016](0016-doors-and-signals.md) | Doors change collision tiles; signals settle in one ordered pass |
