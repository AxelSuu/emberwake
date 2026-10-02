# NPCs: Keeper Hesper and Quill

**Milestone:** M9  **Status:** ready  **Issue:** #131

## Goal
The Quarter has people who answer to what the player has done: the Keeper rewards rescued Lost
Lights, Quill sells the Quarter map, and both stand in different places as the story advances.

## Behavior

- **Who.** Both are `Npc` prefabs (`hesper`, `quill`) with a dialogue graph in
  `content/dialogue.toml`, like the Tinker. LDtk entity types `Hesper` and `Quill`.
- **Stages.** An NPC appears in several spots of the world, one entity per spot, each gated with
  `Requires` and `Unless` on a stage flag ([world flags](world-flags.md)). Stage flags are plain
  integers set by the world (a SetFlag zone or a cutscene), never by the NPC itself:

  | Flag | Value | Quill | Hesper |
  |---|---|---|---|
  | `quill_stage` | 0 | Belfry | |
  | | 1 | Market Square (after the Belfry) | |
  | | 2 | the road to Brass Gardens (after the Lamprey) | |
  | `hesper_stage` | 0 | | by the hub beacon |
  | | 1 | | by the Great Lamp (once it burns) |

  The dialogue reads the same flags, so the lines change with the place.
- **Hesper and the Lost Lights.** Rescuing a Lost Light adds 1 to `lost_lights` (#127). Asking
  Hesper about them pays each threshold once, in order, even when several are owed at once:
  1 light: 50 embers; 2: a flare pouch; 3: an Oil Flask. Paid thresholds are the flags
  `hesper_paid_1..3`. Hesper also explains the Quarter Lamps and the way down to the Cistern.
- **Dialogue actions.** `give:<thing>` (from #118, in `content/grants.toml`) hands out items and
  is reused for the pouch and the flask. `pay:<n>` adds `n` embers to what the player carries.
  `shop:<id>` opens a shop of `content/shop.toml`; the Tinker's is `tinker`, Quill's is `quill`.
- **Quill's shop.** Sells `map.quarter`, a grant (an item, one at most) named after the map's
  area id. Buying spends embers and puts it in the save's `inventory`, so it persists through
  quit and continue, reads as `has.map.quarter` in conditions and is what the map screen (#55)
  checks for `map.<area>`. No save version bump: `inventory` already exists.
- **Shops.** `content/shop.toml` holds one table per shop with its `items`. An item with a `grant`
  adds to that inventory entry instead of counting in a flag.
- **Dev.** The `Npc_Lab` room (`--room Npc_Lab`) has every spot, a beacon and a zone that adds a
  Lost Light; F7 or `--flags quill_stage=1` moves the NPCs.

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| Map price | 30 embers | `content/shop.toml`, `quill.items."map.quarter"` |
| Light 1 reward | 50 embers | Hesper's dialogue |
| Light 2 reward | flare pouch | Hesper's dialogue |
| Light 3 reward | Oil Flask | Hesper's dialogue |

## Acceptance criteria
- [ ] Hesper and Quill can be talked to; their lines exist in English and Swedish.
- [ ] Each NPC is only in the spot its stage flag selects, and moves when the flag changes,
  live and in a fresh room load.
- [ ] Their dialogue changes with the stage flag.
- [ ] Hesper pays each Lost Light threshold once: embers, a flare pouch, an Oil Flask; several
  owed at once are all paid, and nothing is paid twice.
- [ ] Quill sells the map for embers; an unaffordable or already bought map cannot be bought.
- [ ] A bought map is in the save's inventory and survives quit and continue.
- [ ] The Tinker's shop still works unchanged.
- [ ] `--room Npc_Lab` shows every placement.

## Tests
`tests/unit/game/test_shop.py` (shops, grant items), `tests/unit/game/test_npcs.py` (dialogue
graphs against flags), `tests/integration/test_npcs.py` (stages in `Npc_Lab`, Hesper's rewards,
Quill's sale across quit and continue).
