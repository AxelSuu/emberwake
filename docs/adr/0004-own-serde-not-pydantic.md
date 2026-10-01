# 0004 Own serde instead of pydantic at runtime

**Context.** Settings, saves, content defs and level data need typed loading with good errors.
pydantic depends on a compiled core that pygbag does not provide.

**Decision.** `engine.core.serde`: a small dataclass-driven converter (primitives, enums,
literals, dataclasses, lists, tuples, dicts, optionals) with path-precise errors, plus
`VersionedCodec` for envelopes and migrations. Tools use the same models.

**Consequences.** One model set everywhere, zero dependencies, fully tested with hypothesis. We
own the edge cases; JSON Schema export for editor autocomplete is a planned addition.
