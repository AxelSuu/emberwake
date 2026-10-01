# Art bible

## Fundamentals

| Rule | Value |
|---|---|
| Canvas | 640x360, integer upscaled |
| Grid | 16 px tiles |
| Player | ~16x24 px |
| Palette | Resurrect 64 (`game/palette.py`), enforced by `tools/palette lint` |
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
