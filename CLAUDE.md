# Emberwake conventions

Read `docs/architecture.md` before structural changes; decisions live in `docs/adr/`.

## Rules
- Code must stay Python 3.12 compatible (pygbag runs 3.12). Ruff and ty target 3.12.
- `emberwake.engine` never imports `emberwake.game`; `engine.core` never imports
  `engine.platform` or `engine.scene`. `just check` enforces this with import-linter.
- Runtime dependencies: pygame-ce only, plus optional pymunk/moderngl behind feature checks.
  No pydantic or compiled deps at runtime (they break the web build). Use `engine.core.serde`.
- The loop is async; never block. No threads. Long work is split across frames with generators.
- Simulation runs in fixed steps (`Scene.update(dt)` with constant dt). Use seeded
  `random.Random` instances, never the global `random`, so replays stay deterministic.
- Persistent data goes through `Storage` + `VersionedCodec`; bump the version and add a
  migration whenever a saved model changes shape.
- Colors come from `game/palette.py` (Resurrect 64).
- Engine modules get Google-style docstrings (they feed the API docs). Game code: only where
  the why is not obvious.
- New mechanics start as a spec in `docs/specs/` with acceptance criteria.

## Workflow
- `just fix && just check && just test` before every commit.
- Small commits, one logical change each, subject line only, no attribution trailers.
- Never push or touch GitHub without the user's explicit yes.
