"""Optional Ogg Vorbis conversion: the browser build prefers it to WAV, and it is much smaller."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def encoder() -> str | None:
    """The first encoder on PATH (``ffmpeg`` or ``oggenc``), or ``None``."""
    return next((tool for tool in ("ffmpeg", "oggenc") if shutil.which(tool)), None)


def command(tool: str, wav: Path, ogg: Path) -> list[str]:
    if tool == "ffmpeg":
        return ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libvorbis", str(ogg)]
    return ["oggenc", "-Q", "-o", str(ogg), str(wav)]


def to_ogg(wav: Path, tool: str) -> Path:
    """Encode `wav` next to itself as ``.ogg`` and delete the WAV. Raises `OSError` on failure."""
    ogg = wav.with_suffix(".ogg")
    result = subprocess.run(command(tool, wav, ogg), capture_output=True, text=True, check=False)
    if result.returncode != 0 or not ogg.exists():
        raise OSError(f"{tool} failed on {wav}: {result.stderr.strip()}")
    wav.unlink()
    return ogg
