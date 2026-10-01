"""Logging setup: console always, rotating file when a directory is given."""

from __future__ import annotations

import logging
import logging.handlers
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level: int | str = logging.INFO, log_dir: Path | None = None) -> None:
    """Configure the root logger. Safe to call more than once."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(FORMAT, "%H:%M:%S"))
    root.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file = logging.handlers.RotatingFileHandler(
            log_dir / "emberwake.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(file)
