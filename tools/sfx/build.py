"""Build ``sfx/*.toml`` presets into ``assets/sfx/*.wav`` with pitch variants."""

from __future__ import annotations

import tomllib
import zlib
from typing import TYPE_CHECKING

from tools.sfx.ogg import to_ogg
from tools.sfx.synth import SfxError, from_table, render, variant_pitches, write_wav

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def build_file(source: Path, out: Path, ogg: str | None = None) -> list[Path]:
    """Write ``<name>.wav`` and ``<name>_1.wav``... for each ``[sound]`` table in `source`.

    With an `ogg` encoder name, each WAV is converted to ``.ogg`` and removed.
    """
    try:
        data = tomllib.loads(source.read_text())
    except tomllib.TOMLDecodeError as error:
        raise SfxError(f"{source}: {error}") from error
    written = []
    for key, table in data.items():
        name = f"{source.stem}/{key}"
        try:
            params = from_table(table)
        except (SfxError, TypeError) as error:
            raise SfxError(f"{source}: [{key}]: {error}") from error
        seed = zlib.crc32(name.encode())
        for index, pitch in enumerate(variant_pitches(name, params)):
            suffix = f"_{index}" if index else ""
            path = out / source.stem / f"{key}{suffix}.wav"
            write_wav(path, render(params, pitch=pitch, seed=seed + index))
            written.append(to_ogg(path, ogg) if ogg else path)
    return written


def build(
    src: Path, out: Path, report: Callable[[str], None] = print, ogg: str | None = None
) -> int:
    """Build every preset file; returns how many failed."""
    failures = 0
    for source in sorted(src.glob("*.toml")):
        try:
            report(f"{source} -> {len(build_file(source, out, ogg))} files")
        except (SfxError, OSError) as error:
            report(f"error: {error}")
            failures += 1
    return failures
