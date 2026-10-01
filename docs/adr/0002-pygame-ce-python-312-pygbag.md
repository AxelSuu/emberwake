# 0002 pygame-ce, Python 3.12 syntax floor, pygbag as secondary target

**Context.** pygame-ce is the actively developed fork with `FRect`, `fblits`, `Window`,
`gaussian_blur`, `key.get_just_pressed`, `system.get_pref_path`. A browser build is a great
distribution channel but pygbag runs CPython 3.12 and only some packages.

**Decision.** pygame-ce is the only hard runtime dependency. `requires-python >=3.12`, ruff and ty
target 3.12; development may use newer interpreters. The loop is async from day one and CI
builds the web version on every push. The browser uses the software renderer.

**Consequences.** No 3.13+ syntax or stdlib. Compiled extras (moderngl, pymunk, numpy) must be
optional and feature-detected. Retrofitting async later is avoided.
