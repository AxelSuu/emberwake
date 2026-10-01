"""Render rooms headless, as the game draws them, into PNGs.

uv run python -m tools.shot Enemy_Yard                 # -> build/shots/Enemy_Yard.png
uv run python -m tools.shot Lever_Hall --at 120,90     # player feet at world px in the room
uv run python -m tools.shot --all                      # every room
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).parents[2]


def point(text: str) -> tuple[float, float]:
    x, _, y = text.partition(",")
    return float(x), float(y)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.shot", description=__doc__.split("\n\n")[0])
    parser.add_argument("rooms", nargs="*")
    parser.add_argument("--all", action="store_true", help="every room in the world")
    parser.add_argument("--at", type=point, help="player feet, px from the room's top left")
    parser.add_argument("--ticks", type=int, default=90, help="ticks to run before the shot")
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "shots")
    args = parser.parse_args(argv)
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from tools.shot.take import all_rooms, shoot  # noqa: PLC0415

    rooms = all_rooms() if args.all else args.rooms
    if not rooms:
        parser.error("name a room or pass --all")
    args.out.mkdir(parents=True, exist_ok=True)
    for room in rooms:
        print(shoot(room, args.out / f"{room}.png", at=args.at, ticks=args.ticks, scale=args.scale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
