"""Compile ``levels/src`` into ``levels/world.ldtk`` and check it against the prefabs.

uv run python -m tools.levels build            # first build
uv run python -m tools.levels build --merge    # rebuild, keeping rooms made in LDtk
uv run python -m tools.levels validate         # every entity has a prefab its fields fit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.levels.ldtk import build_project
from tools.levels.source import SourceError, load_source
from tools.levels.validate import validate

from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.world.ldtk import load_project

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
    check = commands.add_parser("validate", help="check entities and fields against prefabs")
    check.add_argument("--world", type=Path, default=ROOT / "levels/world.ldtk")
    check.add_argument("--prefabs", type=Path, default=ROOT / "content/prefabs.toml")
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args.world, args.prefabs)

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


def _validate(world: Path, prefabs: Path) -> int:
    problems = validate(load_project(world), load_prefabs(prefabs))
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if not problems:
        print(f"{world.name}: every entity matches {prefabs.name}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
