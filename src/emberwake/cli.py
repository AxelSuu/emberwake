"""Command line options."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class Options:
    """Parsed command line options."""

    dev: bool = False
    fullscreen: bool = False
    log_level: str = "INFO"
    frames: int | None = None


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
    args = parser.parse_args([] if argv is None else argv)
    return Options(
        dev=args.dev, fullscreen=args.fullscreen, log_level=args.log_level, frames=args.frames
    )
