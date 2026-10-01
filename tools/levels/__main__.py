"""Compile ``levels/src`` into ``levels/world.ldtk``.

uv run python -m tools.levels build            # first build
uv run python -m tools.levels build --merge    # rebuild, keeping rooms made in LDtk
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.levels.ldtk import build_project
from tools.levels.source import SourceError, load_source

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.levels", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="compile the source into an LDtk project")
    build.add_argument("--src", type=Path, default=ROOT / "levels/src")
    build.add_argument("--out", type=Path, default=ROOT / "levels/world.ldtk")
    mode = build.add_mutually_exclusive_group()
    mode.add_argument("--merge", action="store_true", help="keep levels made by hand in LDtk")
    mode.add_argument("--force", action="store_true", help="overwrite, dropping hand-made levels")
    args = parser.parse_args(argv)

    out: Path = args.out
    if out.exists() and not (args.merge or args.force):
        print(f"{out} exists; pass --merge (or --force to drop hand-made levels)", file=sys.stderr)
        return 1
    previous = json.loads(out.read_text(encoding="utf-8")) if args.merge and out.exists() else None
    try:
        source = load_source(args.src)
        project = build_project(source, previous)
    except SourceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(project, indent="\t") + "\n", encoding="utf-8")
    generated = len(source.rooms)
    print(f"Wrote {out}: {generated} generated, {len(project['levels']) - generated} kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
