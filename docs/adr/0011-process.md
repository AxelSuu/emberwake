# 0011 Process: specs, ADRs, GitHub issues, CI gates

**Context.** Development is long-running, part-time and partly agent-driven, so intent must be
written down where both people and agents find it.

**Decision.** Living GDD; one spec per mechanic with acceptance criteria before implementation;
ADRs for structural decisions; GitHub issues and milestones mirror the roadmap; CI runs ruff, ty,
import-linter, tests and the web build on every push. Small single-purpose commits.

**Consequences.** Slight writing overhead per feature, in exchange for reviewable intent and
fewer regressions.
