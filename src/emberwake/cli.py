"""Command line options."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.game.data.save import SLOTS

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class Options:
    """Parsed command line options."""

    dev: bool = False
    fullscreen: bool = False
    log_level: str = "INFO"
    frames: int | None = None
    room: str | None = None
    replay: str | None = None
    slot: int = 1
    new: bool = False


def parse_args(argv: Sequence[str] | None = None) -> Options:
    """Parse `argv`; ``None`` means no arguments (the browser build has none)."""
    parser = argparse.ArgumentParser(prog="emberwake", description="Carry light into the dark.")
    parser.add_argument("--dev", action="store_true", help="enable developer tools (F1 overlay)")
    parser.add_argument("--fullscreen", action="store_true", help="start in fullscreen")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    parser.add_argument(
        "--frames", type=int, metavar="N", help="quit after N frames (smoke tests, profiling)"
    )
    parser.add_argument("--room", help="start directly in this LDtk level")
    parser.add_argument("--replay", metavar="KEY", help="play a saved replay, e.g. replays/x.json")
    parser.add_argument(
        "--slot", type=int, choices=SLOTS, default=1, help="save slot to continue and save to"
    )
    parser.add_argument("--new", action="store_true", help="start a new game in the slot")
    args = parser.parse_args([] if argv is None else argv)
    return Options(
        dev=args.dev,
        fullscreen=args.fullscreen,
        log_level=args.log_level,
        frames=args.frames,
        room=args.room,
        replay=args.replay,
        slot=args.slot,
        new=args.new,
    )
