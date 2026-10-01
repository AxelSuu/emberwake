# 0005 LDtk for levels

**Context.** Candidates: Tiled + PyTMX, LDtk, a custom editor.

**Decision.** LDtk. Auto-layer rules turn IntGrid collision paint into decorated tiles, entities
have typed fields and entity references (wiring levers to doors), the GridVania world layout maps
directly to rooms, and levels can be saved as separate files. A small typed loader reads LDtk JSON
directly; `tools/ldtk validate` checks entity fields against content definitions in CI.

**Consequences.** No PyTMX. Hot reload works by re-reading the JSON. We depend on LDtk's JSON
format (stable, versioned); the loader isolates it.
