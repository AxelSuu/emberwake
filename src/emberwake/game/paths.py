"""Where runtime data (content/, levels/) lives.

The repo root in development, the bundle root in the browser build. Override with the
EMBERWAKE_ROOT environment variable.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path


@cache
def data_root() -> Path:
    if env := os.environ.get("EMBERWAKE_ROOT"):
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if (parent / "content").is_dir() and (parent / "levels").is_dir():
            return parent
    msg = "content/ and levels/ not found; set EMBERWAKE_ROOT"
    raise FileNotFoundError(msg)


def content(name: str) -> Path:
    return data_root() / "content" / name


def levels(name: str) -> Path:
    return data_root() / "levels" / name


def sounds() -> Path:
    return data_root() / "assets" / "sfx"


def sprites() -> Path:
    return data_root() / "assets" / "sprites"
