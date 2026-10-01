"""Compile ``.pxl`` sprites to PNG sheets, and recompile when they change."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import pygame
from tools.pxl.spec import TRANSPARENT, PxlError, Sprite, parse

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def render(sprite: Sprite) -> pygame.Surface:
    """A horizontal sheet with one cell per frame."""
    width, height = sprite.size
    sheet = pygame.Surface((width * len(sprite.frames), height), pygame.SRCALPHA)
    for index, layers in enumerate(sprite.frames):
        for rows in layers:
            for y, row in enumerate(rows):
                for x, char in enumerate(row):
                    if char != TRANSPARENT:
                        sheet.set_at((index * width + x, y), (*sprite.palette[char], 255))
    return sheet


def output_path(source: Path, art: Path, assets: Path) -> Path:
    """Where `source` (under `art`) compiles to under `assets`."""
    return assets / source.relative_to(art).with_suffix(".png")


def compile_file(source: Path, art: Path, assets: Path) -> Path:
    """Write the sheet, plus a ``.json`` of frame size and durations when it has several frames."""
    sprite = parse(source)
    out = output_path(source, art, assets)
    out.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(render(sprite), out)
    meta = out.with_suffix(".json")
    if len(sprite.frames) > 1:
        info = {"frame": list(sprite.size), "frames": len(sprite.frames), "ms": sprite.ms}
        meta.write_text(json.dumps(info) + "\n")
    else:
        meta.unlink(missing_ok=True)
    return out


def sources(art: Path) -> list[Path]:
    return sorted(art.glob("**/*.pxl"))


def build(art: Path, assets: Path, report: Callable[[str], None] = print) -> int:
    """Compile every sprite; returns how many failed."""
    failures = 0
    for source in sources(art):
        try:
            report(f"{source} -> {compile_file(source, art, assets)}")
        except PxlError as error:
            report(f"error: {error}")
            failures += 1
    return failures


def watch(
    art: Path,
    assets: Path,
    report: Callable[[str], None] = print,
    *,
    interval: float = 0.3,
    rounds: int | None = None,
) -> None:
    """Poll `art` and recompile sprites as they change, until interrupted (or `rounds` ends)."""
    seen: dict[Path, float] = {}
    while rounds is None or rounds > 0:
        for source in sources(art):
            stamp = source.stat().st_mtime_ns
            if seen.get(source) != stamp:
                seen[source] = stamp
                try:
                    report(f"{source} -> {compile_file(source, art, assets)}")
                except PxlError as error:
                    report(f"error: {error}")
        if rounds is not None:
            rounds -= 1
        time.sleep(interval)
