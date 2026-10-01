# 0001 Genre: light-driven action-platformer

**Context.** The project needs a genre that rewards depth over months and exercises camera work,
large worlds, lighting, parallax, physics and animation, while staying feasible in pygame-ce.

**Decision.** A 2D side-scrolling action-platformer with metroidvania structure where light is
the core mechanic (see `gdd.md`). Trials add score, medals and ghosts for replayability.

**Consequences.** Dynamic lighting becomes a gameplay requirement, which justifies the rendering
investment. Tight kinematic platforming is a known strength of pygame. Content cost is high;
the vertical slice is scoped to one biome.
