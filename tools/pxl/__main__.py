"""Compile pixel DSL sprites (``art/**/*.pxl``) into PNG sheets under ``assets/``.

uv run python -m tools.pxl build     # compile everything
uv run python -m tools.pxl watch     # recompile on save
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from tools.pxl.build import build, watch

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def _errors_only(line: str) -> None:
    if line.startswith("error"):
        print(line)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.pxl", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (("build", "compile every sprite"), ("watch", "recompile on change")):
        command = commands.add_parser(name, help=text)
        command.add_argument("--art", type=Path, default=ROOT / "art")
        command.add_argument("--assets", type=Path, default=ROOT / "assets")
        command.add_argument("--quiet", action="store_true", help="report only errors")
    args = parser.parse_args(argv)
    report = _errors_only if args.quiet else print
    if args.command == "watch":
        try:
            watch(args.art, args.assets, report)
        except KeyboardInterrupt:
            return 0
        return 0
    return 1 if build(args.art, args.assets, report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
