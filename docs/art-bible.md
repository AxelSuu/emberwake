# Art bible

## Fundamentals

| Rule | Value |
|---|---|
| Canvas | 640x360, integer upscaled |
| Grid | 16 px tiles |
| Player | ~16x24 px |
| Palette | Resurrect 64 (`game/palette.py`), enforced by `python -m tools.palette lint` (in `just check`: PNG pixels, TOML and game-code hex literals) |
| Outlines | Dark selective outlines (INK `#2e222f`), never pure black |
| Mood | Cold desaturated blues, plums and teals in darkness; warm ambers for light |

## Maps per sprite

Each sprite may ship up to three aligned images, packed together by the atlas packer:

- **albedo**: the colors, unlit.
- **normal**: generated from an alpha distance-field bevel, optionally guided by a hand-painted
  height layer. Used by the GL lighting pass.
- **emissive**: pixels that glow on their own (lantern core, eyes, beacon fire). Feed bloom.

## Pipeline

1. Placeholder art from code, so gameplay never waits for art.
2. Pixel DSL (`art/**/*.pxl`, TOML): palette keys + text grids + frames + layers, compiled to
   PNG. Diffable and easy to author by hand or by an AI assistant. Tiles, props, icons, UI.
   `just art` compiles `art/**/*.pxl` to `assets/**/*.png` (a sheet, plus a `.json` of frame size
   and timings when there are several frames); `just art-watch` recompiles on save; `just run`
   compiles first. `uses = "base"` pulls in the shared keys of `art/palettes/base.toml`. The
   format is documented at the top of `tools/pxl/spec.py`.
   - **Finished sprites** go in `art/sprites/<name>.pxl`, where `<name>` is the name gameplay
     uses (`clockrat`, `beacon_lit`, see `content/prefabs.toml`). The sprite bank
     (`game/render/bank.py`) shows them instead of the placeholder, anchored at the bottom
     centre of the entity, looping multi-frame sheets.
   - **Ideas** go in `art/lab/<subject>/<idea>.pxl` and never reach the game. `just sheet
     art/lab/<subject>` renders every idea's frames on a dark, a lit and a mid-tone panel into
     `build/sheets/<subject>.png`, so many variants are compared side by side; favourites move
     to `art/sprites`.
   - **In place**: `just shot <room> --at x,y` renders a room headless as the game draws it, into
     `build/shots/<room>.png`.
3. Aseprite files for hand-drawn work, exported through the CLI or parsed directly.
4. Autotile generator: 47-tile blob sets from a few base pieces, plus matching LDtk rules.
5. Free CC0 packs only to validate the pipeline early, replaced before release.

## Animation

| Anim | Frames | Notes |
|---|---|---|
| Idle | 4-6 | Lantern sway |
| Run | 8 | Footstep events on contact frames |
| Jump / fall | 2 + 2 | Plus squash and stretch in code |
| Dash | 3 | Afterimages in code |
| Attack | 5 | Hitbox active frames tagged |

Bosses and large creatures use the skeletal rig (parts rotated through a RotSprite angle cache
so pixels stay crisp). Secondary motion (scarf, cape, chains) is procedural verlet.

## Light conventions

- Light comes from in-world sources only; ambient per room is defined in LDtk.
- Relit areas swap from the "dark" LUT to the "lit" LUT over ~2 seconds.
- Foreground occluders are darkened and blurred; far parallax layers are desaturated.

## Fonts and audio

- Pixel fonts: m5x7 / m6x11 (Daniel Linssen, attribution in credits) until a custom bitmap font.
- SFX: procedural sfxr-style generator plus pitch variants; music as layered OGG stems.
