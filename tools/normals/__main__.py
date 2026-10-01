"""Generate normal maps next to albedo PNGs.

uv run python -m tools.normals          # every sprite under assets/
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from tools.normals.generate import generate

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.normals", description=__doc__.split("\n\n")[0])
    parser.add_argument("--assets", type=Path, default=ROOT / "assets")
    parser.add_argument("--radius", type=int, default=2, help="bevel width in pixels")
    parser.add_argument("--strength", type=float, default=2.0)
    parser.add_argument("--depth", type=float, default=1.0, help="weight of the _h height layer")
    args = parser.parse_args(argv)
    written = generate(args.assets, radius=args.radius, strength=args.strength, depth=args.depth)
    print(f"{len(written)} normal maps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
