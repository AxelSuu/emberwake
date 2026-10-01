# 0003 Deterministic fixed-step simulation in an async loop

**Context.** Variable timesteps make physics feel inconsistent and make replays impossible.

**Decision.** Simulation advances in fixed 1/60 s steps (`FixedStep`), rendering runs free with an
interpolation `alpha`. All randomness goes through seeded `random.Random` instances. Input is
sampled per step so it can be recorded.

**Consequences.** Replays, Trial ghosts, bug repro files and headless scenario tests come almost
for free. Slow machines run several steps per frame (clamped at 0.25 s to avoid a spiral).
