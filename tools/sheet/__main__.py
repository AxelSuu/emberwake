"""Render a folder of ``.pxl`` sketches into one contact sheet PNG.

uv run python -m tools.sheet art/lab/player             # -> build/sheets/player.png
uv run python -m tools.sheet art/lab --scale 2          # every lab folder, one sheet each
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
from tools.sheet.render import contact_sheet

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def sheets(folder: Path, out: Path, scale: int) -> list[Path]:
    """One sheet per folder holding sketches: `folder` itself, or each folder under it."""
    if any(folder.glob("*.pxl")):
        folders = [folder]
    else:
        folders = sorted(p for p in folder.iterdir() if p.is_dir())
    written = []
    for each in folders:
        paths = sorted(each.glob("*.pxl"))
        if not paths:
            continue
        target = out / f"{each.name}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(contact_sheet(paths, scale), target)
        written.append(target)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.sheet", description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "sheets")
    parser.add_argument("--scale", type=int, default=3)
    args = parser.parse_args(argv)
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    for path in sheets(args.folder, args.out, args.scale):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
