# 0007 Hybrid physics: kinematic characters, pymunk props

**Context.** Rigid-body engines make platformer controls feel floaty; hand-rolled physics cannot
do ropes, chains and tumbling debris well.

**Decision.** Characters use custom swept-AABB kinematics against the tile grid, tuned for feel
(coyote time, buffers, corner correction). Props, ropes, debris and flares use pymunk; static
tiles are greedy-meshed into boxes and the player is mirrored as a kinematic body. No slopes in
v1.

**Consequences.** Precise controls plus satisfying physical props. pymunk is optional: if it is
missing (browser), props fall back to simple kinematics.
