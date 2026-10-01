# 0010 Art pipeline: Resurrect 64, 16 px, pixel DSL, generated normals

**Context.** The game needs a lot of consistent pixel art, authored partly by people and partly by
code or an AI assistant, plus normal maps for lighting.

**Decision.** Resurrect 64 palette, 16 px grid, 640x360 canvas (see `art-bible.md`). Sources are a
text-based pixel DSL (diffable, scriptable) and Aseprite files. Normal maps are generated from
alpha distance-field bevels with optional height layers. An atlas packer packs albedo, normal and
emissive maps in lockstep. Placeholder art first, always.

**Consequences.** Tooling work up front (M6), but art can be iterated in code review and stays
on-palette automatically.
