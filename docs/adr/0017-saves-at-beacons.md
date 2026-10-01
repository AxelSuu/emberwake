# 0017 Saves at beacons and on quit; replays never save

Plan decisions D3 and D6 in `docs/plans/m2-world.md`.

**Context.** Players need progress that survives quitting, on desktop and in the browser.
Replays and dev shortcuts (`--room`) must not corrupt it, and replays must stay deterministic.

**Decision.** Three save slots, `saves/slot_N.json`, through `Storage` and a `VersionedCodec`.
A slot stores progress, not position: the last beacon (or the starting room), playtime, flags,
world state by iid, discovered rooms and stats. Relighting a beacon saves and makes it the
continue point; quitting saves too, keeping the continue point. Hazard deaths still respawn at
the room entrance. A session started with `--room` or a replay starts from a fresh world and
never saves; a replay covers one session from a known start.

**Consequences.** Quitting mid-room loses only your position, so there is no save-anywhere
exploit and no need to serialize live physics. Replays of sessions that continued from a slot
would need the slot's world state recorded too; that is deferred to Trials (M8). The browser
build saves at beacons, since a closing tab never runs the quit path.
