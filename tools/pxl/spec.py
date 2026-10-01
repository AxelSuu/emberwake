"""Parse and check a ``.pxl`` sprite.

```toml
[palette]                  # one character per color; "." is always transparent
o = "#2e222f"
f = "#fb6b1d"

[layers]                   # named grids, one character per pixel, all the same size
body = '''
.oo.
oooo
'''
flame = '''
.f..
....
'''

[[frames]]                 # optional; layers are drawn bottom to top
layers = ["body", "flame"]
ms = 120                   # optional duration, for animation sheets
```

Without ``[[frames]]`` the sprite is one frame of every layer in order.

``uses = "base"`` at the top merges in the shared palette ``palettes/base.toml``, found in the
sprite's folder or the nearest folder above it; keys in the sprite's own ``[palette]`` win.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import SerdeError, from_data

if TYPE_CHECKING:
    from pathlib import Path

TRANSPARENT = "."


class PxlError(ValueError):
    """The sprite source is inconsistent; the message says where."""


@dataclass(slots=True)
class FrameSpec:
    layers: list[str]
    ms: int = 100


@dataclass(slots=True)
class PxlFile:
    uses: str = ""
    palette: dict[str, str] = field(default_factory=dict)
    layers: dict[str, str] = field(default_factory=dict)
    frames: list[FrameSpec] = field(default_factory=list)


@dataclass(slots=True)
class Sprite:
    """A checked sprite: `size` px per frame, each frame a list of layer grids, bottom first."""

    size: tuple[int, int]
    palette: dict[str, tuple[int, int, int]]
    frames: list[list[list[str]]]
    ms: list[int]


def grid(text: str) -> list[str]:
    """Rows of a layer, ignoring blank lines and surrounding whitespace."""
    return [row.strip() for row in text.strip().splitlines() if row.strip()]


def parse(path: Path) -> Sprite:
    """Read and check `path`. Raises `PxlError` naming the file and the problem."""
    try:
        raw = from_data(PxlFile, tomllib.loads(path.read_text(encoding="utf-8")))
        if raw.uses:
            raw.palette = {**shared_palette(path, raw.uses), **raw.palette}
        return check(raw)
    except (tomllib.TOMLDecodeError, SerdeError, PxlError) as error:
        msg = f"{path}: {error}"
        raise PxlError(msg) from error


def shared_palette(path: Path, name: str) -> dict[str, str]:
    """The ``[palette]`` of ``palettes/<name>.toml`` nearest above `path`."""
    for folder in path.resolve().parents:
        candidate = folder / "palettes" / f"{name}.toml"
        if candidate.is_file():
            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            return from_data(dict[str, str], data.get("palette", {}))
    msg = f"no palettes/{name}.toml above the sprite"
    raise PxlError(msg)


def check(raw: PxlFile) -> Sprite:
    palette: dict[str, tuple[int, int, int]] = {}
    for key, color in raw.palette.items():
        if len(key) != 1 or key == TRANSPARENT:
            msg = f"palette key {key!r} must be one character other than {TRANSPARENT!r}"
            raise PxlError(msg)
        palette[key] = _rgb(color)
    if not raw.layers:
        msg = "no [layers]"
        raise PxlError(msg)
    grids = {name: grid(text) for name, text in raw.layers.items()}
    sizes = {(len(rows[0]) if rows else 0, len(rows)) for rows in grids.values()}
    if len(sizes) != 1 or (0, 0) in sizes:
        msg = "layers must be non-empty and the same size"
        raise PxlError(msg)
    (size,) = sizes
    for name, rows in grids.items():
        for y, row in enumerate(rows):
            if len(row) != size[0]:
                msg = f"layer {name!r} row {y + 1} is {len(row)} wide, expected {size[0]}"
                raise PxlError(msg)
            for x, char in enumerate(row):
                if char != TRANSPARENT and char not in palette:
                    msg = f"layer {name!r} {x + 1},{y + 1}: {char!r} is not in the palette"
                    raise PxlError(msg)
    frames = raw.frames or [FrameSpec(list(grids), 0)]
    for index, frame in enumerate(frames, 1):
        for name in frame.layers:
            if name not in grids:
                msg = f"frame {index} uses unknown layer {name!r}"
                raise PxlError(msg)
    stacks = [[grids[name] for name in frame.layers] for frame in frames]
    return Sprite(size, palette, stacks, [frame.ms for frame in frames])


def _rgb(color: str) -> tuple[int, int, int]:
    if len(color) != 7 or not color.startswith("#"):
        msg = f"color {color!r} is not #rrggbb"
        raise PxlError(msg)
    try:
        value = int(color[1:], 16)
    except ValueError:
        msg = f"color {color!r} is not #rrggbb"
        raise PxlError(msg) from None
    return value >> 16, (value >> 8) & 255, value & 255
