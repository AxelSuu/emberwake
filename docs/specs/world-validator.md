# World validator

**Milestone:** M9  **Status:** done  **Issue:** #128

## Goal
A level that cannot be finished, an entrance without a respawn point or a gate that waits for a
flag nobody sets fails `just check` instead of surfacing in playtests.

## Behavior
Part of `tools.levels validate`. Pure functions over the loaded levels and the content files
(`grants.toml`, `dialogue.toml`, `shop.toml`, `trials.toml`); no pygame, a fraction of a second.

- **Wiring.** Every entity ref in a `Targets` field names an entity that exists in some level.
- **Flags.** Every flag a `Requires`, `Unless` or `Condition` reads is written somewhere: a
  SetFlag, a dialogue `set` or `add`, a shop item's flag, or a flag the game sets itself
  (`Rules.code_flags`: the Lamprey's `lamprey_drained` and `lamprey_defeated`). Every `has.<thing>` names a key of
  `grants.toml` and the thing is given somewhere: a starting ability, a Grant pickup or a dialogue
  `give:<thing>`. A Grant's `Thing` must be a key of `grants.toml`.
- **Entrances.** An entrance is a stretch of a shared room edge that is open on both sides (two
  tiles tall for side-by-side rooms, since the player is 20 px high). Each room on it has a
  PlayerStart within 6 tiles of it. Rooms of the `lab` area are skipped.
- **Reachability.** The start room is `DEFAULT_ROOM`. When it is absent or in `lab` nothing is
  checked, so dev worlds pass. Otherwise a search over the collision tiles of every room, with the
  abilities and facts available so far, grows until nothing changes:
  - *Movement* is tile based and generous: walk, drop through one-ways, jump up 3 tiles and across
    6, wall jumps refill the jump, the `dash` ability adds 2 up and 4 across. Hazards, closed doors
    and the void block; a Lightform is a one-way.
  - *Doors* open once their sources are available: a Lever or PressurePlate the search reaches, a
    FlagSwitch whose condition holds. Mode `all` needs every source; an inverted door is open.
  - *Facts* grow from what the search reaches: a Grant gives its thing, a SetFlag sets or adds, an
    NPC runs its whole dialogue (flags, `give:`, the shop). An entity counts once its `Requires`
    holds; `Unless` is ignored, since it can only take things away later. A flag some SetFlag adds
    to is assumed to take any value.
  - Every room outside `lab` and outside the trials (reached from the menu) must be reached.
    The message says what would unlock the room: an ability and where it is granted, a door and
    its sources, or that no open passage leads there. A room that needs an ability granted only
    behind it, or later than the room needs it, is such a case, so the critical path never needs
    a later ability.

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| `NEAR` | 6 tiles | PlayerStart distance from an entrance |
| jump up, across | 3, 6 tiles | The player-movement spec peaks at 3.5 to 4.5 and clears 6 |
| dash up, across | +2, +4 tiles | A dash covers about 4.5 tiles |

## Acceptance criteria
- [x] A Targets ref to a missing entity is reported.
- [x] A Requires, Unless or Condition on a flag nothing sets is reported; so are an unknown or
  never given `has.<thing>` and a Grant of an unknown thing.
- [x] An open room edge without a PlayerStart near it is reported on each side; lab rooms are not.
- [x] A room with no open passage to the rest of the world is reported unreachable.
- [x] A room behind a door whose lever is unreachable, or whose FlagSwitch flag is never set, is
  reported with the door; one whose lever is reachable passes.
- [x] A room beyond a gap too wide for the abilities available by then is reported with the
  ability that crosses it and where it is granted; it passes once a Grant for it is reachable.
- [x] A flag set by a reachable SetFlag or dialogue opens what it gates, and an ability granted
  by reachable NPC dialogue counts.
- [x] A lab or absent start room skips reachability; trial rooms are exempt.
- [x] The committed world passes, and a missing PlayerStart at an entrance of a quarter room is
  fixed in the levels.

## Tests
`tests/unit/tools/test_world_validate.py`: small synthetic worlds, one per failure above.
