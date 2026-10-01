"""Pack sprites into albedo, normal and emissive atlases.

uv run python -m tools.atlas            # assets/ -> build/atlas/
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from tools.atlas.pack import AtlasError, pack

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.atlas", description=__doc__.split("\n\n")[0])
    parser.add_argument("--assets", type=Path, default=ROOT / "assets")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "atlas")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--padding", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        manifest = pack(args.assets, args.out, width=args.width, padding=args.padding)
    except AtlasError as error:
        print(f"error: {error}")
        return 1
    print(f"{len(manifest['sprites'])} sprites -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
