# 0007 Hybrid physics: kinematic characters, pymunk props

**Context.** Rigid-body engines make platformer controls feel floaty; hand-rolled physics cannot
do ropes, chains and tumbling debris well.

**Decision.** Characters use custom swept-AABB kinematics against the tile grid, tuned for feel
(coyote time, buffers, corner correction). Props, ropes, debris and flares use pymunk; static
tiles are greedy-meshed into boxes and the player is mirrored as a kinematic body. No slopes in
v1.

**Consequences.** Precise controls plus satisfying physical props. pymunk is optional: if it is
missing (browser), props fall back to simple kinematics.

**Implementation note.** `engine/physics/props.py` has `PropWorld` with two backends, chosen at
import time by `HAS_PYMUNK`. The pymunk backend meshes solid tiles greedily into static boxes and
mirrors the player as a kinematic body; the fallback gives props gravity, bounce and friction
through the tile mover, without prop-prop or player collision. Whether pymunk runs in the browser
build is still open (issue #2); the fallback is what the web build uses until it is checked.

**Pushable crates (#124).** Crates are not on `PropWorld`. They are axis-aligned boxes stepped by
`kinematic.move` with `solids`, which the player's own collision also reads, so stacking, standing
on them and replays behave the same with or without pymunk. See `docs/specs/push-crates.md`.
