# Map screen

**Milestone:** M9  **Status:** done  **Issue:** #55

## Goal
The player can see where they have been in the current area, where to rest and where their
embers lie, and buying an area's map from Quill shows the rooms still to find.

## Behavior

- **Opening.** `Map` in the pause menu, or `M` while playing (not in a Trial). Back, Escape or
  `M` closes it and returns to the game, which stays paused underneath.
- **What it shows.** The rooms of the area the player is in (the level field `Area`), drawn
  from their LDtk rects, scaled to fit the screen with a margin and centred. A room is drawn:
  - filled, if it has been entered (its iid is in the save's `discovered`);
  - as an outline, if not, but the player owns the area's map (`map.<area>` in the inventory);
  - not at all otherwise.
  Each room is drawn one pixel smaller on each side, so neighbours read as separate rooms.
- **Icons**, only in drawn rooms:
  - a beacon: bright once lit, dim while cold. Lit comes from the live world for loaded rooms
    and from the saved world state otherwise (the pause snapshot makes both agree);
  - an NPC (any entity whose prefab has `Npc`): only where its `Requires` and `Unless` place it
    now, so Quill shows in the Belfry or the Square by stage;
  - the Cinder, if it lies in this area;
  - the player, blinking.
- **Title.** The area's name and light %, as in the pause menu.
- The view is computed once on opening (`map_view`, a pure function of the levels, the save and
  the live positions); nothing moves while it is open.

## Tuning parameters
| Name | Default | Notes |
|---|---|---|
| margin | 24 px | canvas border kept clear around the area |
| title gap | 28 px | space above the area for its name |
| blink | 0.5 s | the player icon's on/off period |

## Acceptance criteria
- [x] Entered rooms of the current area are filled; rooms of other areas are not drawn.
- [x] Unentered rooms are hidden without the map and outlined with it.
- [x] Lit and cold beacons, NPCs where their stage puts them, the Cinder and the player are
  placed at their world positions, scaled like the rooms.
- [x] The area's bounding box fits inside the canvas minus the margins, centred, with its
  aspect kept.
- [x] The pause menu's Map and the `M` key open it; Back closes it.

## Tests
`tests/unit/game/test_map.py` (the view from synthetic levels), `tests/integration/test_map.py`
(opening from the pause menu and with `M`, the bought map, drawing).
