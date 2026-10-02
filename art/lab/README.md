# Art lab

Ideas, not finished art. Each folder is a subject; each `.pxl` file one idea, with a note at the
top saying what it is going for. The game never loads anything from here.

    just sheet art/lab            # every subject -> build/sheets/<subject>.png
    just sheet art/lab/player     # one subject

A sheet shows each frame three times: in a dark room (only what glows shows; this is how most
of the game is seen), lit by a lantern, and flat to read the colors. Tilesets (four 16 px source
tiles in a row: fill, top edge, outer corner, inner corner) are shown composed into a patch of
terrain by the autotiler.

## Picking

Say which letters you like per subject (for example "player: d, h; clockrat: c"). Favourites get
iterated on here (more variants of the chosen direction, then animation), and the winner moves
to `art/sprites/<name>.pxl`, where the game picks it up in place of the placeholder.

| Subject | Ideas | Size |
|---|---|---|
| player | a hood, b lamplighter, c candle, d diver, e mothling, f wick, g masked, h cage | 16x24 |
| clockrat | a windup, b gearwheel, c lampeye, d skeleton, e teapot, f tinmouse | 16x16 |
| gloomcrawler | a inkblob, b spider, c hunch, d tar, e smokemask | 16x16 |
| wisp_eater | a moth, b angler, c jelly, d lampbat, e eyecloud | 16x16 |
| tinker | a goggles, b old hunched, c automaton, d frog | 16x24 |
| lamp_post | a victorian, b gas globe, c bent, d gallows cage, e bell lamp, f wall sconce | 16x48 |
| beacon | a lighthouse, b brazier pillar, c clock face, d shrine | 32x48 |
| tiles | a wet brick, b cobble, c riveted iron, d carved block | 4 x 16x16 |

Colors come from `art/palettes/base.toml` (`uses = "base"`). Pixels in the flame and mint
colors (`palette.EMISSIVE`) glow in the dark, so keep them for things that give off light.
