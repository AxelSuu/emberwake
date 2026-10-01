"""Generate sound effects from presets.

uv run python -m tools.sfx              # sfx/*.toml -> assets/sfx/
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from tools.sfx.build import build

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.sfx", description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", type=Path, default=ROOT / "sfx")
    parser.add_argument("--out", type=Path, default=ROOT / "assets" / "sfx")
    args = parser.parse_args(argv)
    return 1 if build(args.src, args.out) else 0


if __name__ == "__main__":
    raise SystemExit(main())
