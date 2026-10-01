# 0008 GL and software render backends

**Context.** Normal-mapped lighting, soft shadows, bloom, color grading and HD-2D depth of field
need shaders. The browser build and weak machines cannot rely on them.

**Decision.** Gameplay emits a backend-agnostic `RenderFrame`. The GL backend (moderngl, desktop)
renders albedo, normal and emissive buffers and runs deferred lighting plus post effects. The
software backend approximates lighting with additive gradients multiplied over the scene and uses
pre-blurred parallax layers for depth of field.

**Consequences.** Same game code on every platform, graceful degradation, visual tests per
backend. Two backends to maintain; features land in GL first and get a cheap software
approximation.
