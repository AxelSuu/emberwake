"""Generate sound effects from presets.

uv run python -m tools.sfx              # sfx/*.toml -> assets/sfx/
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from tools.sfx.build import build
from tools.sfx.ogg import encoder

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.sfx", description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", type=Path, default=ROOT / "sfx")
    parser.add_argument("--out", type=Path, default=ROOT / "assets" / "sfx")
    parser.add_argument(
        "--ogg",
        choices=("auto", "always", "never"),
        default="auto",
        help="convert to Ogg Vorbis (needs ffmpeg or oggenc); auto does so when one is found",
    )
    args = parser.parse_args(argv)
    tool = None if args.ogg == "never" else encoder()
    if args.ogg == "always" and tool is None:
        print("error: --ogg always needs ffmpeg or oggenc on PATH")
        return 1
    if args.ogg == "auto" and tool is None:
        print("note: no ogg encoder found, keeping WAV (install ffmpeg for smaller web builds)")
    return 1 if build(args.src, args.out, ogg=tool) else 0


if __name__ == "__main__":
    raise SystemExit(main())
