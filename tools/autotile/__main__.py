"""Expand four source tiles (fill, edge, outer, inner) into a 47-tile blob set and LDtk rules.

uv run python -m tools.autotile art/tiles/ground.png    # -> assets/tiles/ground.png + .rules.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from tools.autotile.blob import build

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.autotile", description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, default=Path("assets/tiles"))
    args = parser.parse_args(argv)
    try:
        png, rules = build(args.source, args.out)
    except ValueError as error:
        print(f"error: {error}")
        return 1
    print(f"{args.source} -> {png}, {rules}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
