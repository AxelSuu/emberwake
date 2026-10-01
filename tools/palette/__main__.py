"""Check that art, content and game code only use Resurrect 64 colors.

uv run python -m tools.palette lint
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.palette.lint import lint

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.palette", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("lint", help="list off-palette colors")
    check.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    offenders = lint(args.root)
    for offender in offenders:
        print(offender, file=sys.stderr)
    if offenders:
        return 1
    print("palette: every color is in Resurrect 64")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
