"""An sfxr-style synthesizer: one parameter set in, 16-bit mono samples out."""

from __future__ import annotations

import math
import random
import struct
import wave
import zlib
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

RATE = 22050
WAVES = ("square", "saw", "sine", "triangle", "noise")


class SfxError(ValueError):
    pass


@dataclass(frozen=True)
class Params:
    """Seconds, hertz and 0..1 unless noted."""

    wave: str = "square"
    freq: float = 440.0
    slide: float = 0.0  # octaves per second
    duty: float = 0.5
    attack: float = 0.01
    sustain: float = 0.1
    decay: float = 0.1
    vibrato_depth: float = 0.0  # octaves
    vibrato_rate: float = 8.0
    lowpass: float = 1.0  # 1 = off
    volume: float = 0.5
    variants: int = 0
    pitch_spread: float = 0.12  # octaves, +/- per variant

    def __post_init__(self) -> None:
        if self.wave not in WAVES:
            raise SfxError(f"wave must be one of {', '.join(WAVES)}, not {self.wave!r}")
        if not 0 < self.freq < RATE / 2:
            raise SfxError(f"freq out of range: {self.freq}")
        if min(self.attack, self.sustain, self.decay) < 0 or self.length <= 0:
            raise SfxError("envelope times must be non-negative and not all zero")
        if not 0 < self.lowpass <= 1 or not 0 <= self.volume <= 1:
            raise SfxError("lowpass is in (0, 1] and volume in [0, 1]")

    @property
    def length(self) -> float:
        return self.attack + self.sustain + self.decay


def from_table(table: dict) -> Params:
    known = {f.name for f in fields(Params)}
    extra = set(table) - known
    if extra:
        raise SfxError(f"unknown parameters: {', '.join(sorted(extra))}")
    return Params(**table)


def envelope(p: Params, t: float) -> float:
    if t < p.attack:
        return t / p.attack
    if t < p.attack + p.sustain:
        return 1.0
    return max(0.0, 1.0 - (t - p.attack - p.sustain) / p.decay) if p.decay else 0.0


def render(p: Params, *, pitch: float = 0.0, seed: int = 0) -> list[int]:
    """Samples for `p`, shifted by `pitch` octaves; `seed` only matters for noise."""
    rng = random.Random(seed)
    count = round(p.length * RATE)
    phase = 0.0
    held = rng.uniform(-1, 1)
    smooth = 0.0
    out = []
    for i in range(count):
        t = i / RATE
        octaves = pitch + p.slide * t + p.vibrato_depth * math.sin(math.tau * p.vibrato_rate * t)
        previous = phase
        phase = (phase + p.freq * 2**octaves / RATE) % 1.0
        if p.wave == "noise":
            if phase < previous:
                held = rng.uniform(-1, 1)
            value = held
        elif p.wave == "square":
            value = 1.0 if phase < p.duty else -1.0
        elif p.wave == "saw":
            value = 2.0 * phase - 1.0
        elif p.wave == "triangle":
            value = 4.0 * abs(phase - 0.5) - 1.0
        else:
            value = math.sin(math.tau * phase)
        smooth += (value - smooth) * p.lowpass
        out.append(round(smooth * envelope(p, t) * p.volume * 32767))
    return out


def variant_pitches(name: str, p: Params) -> list[float]:
    """Pitch offsets (octaves) for the base sound then each variant; stable per name."""
    rng = random.Random(zlib.crc32(name.encode()))
    return [0.0] + [rng.uniform(-p.pitch_spread, p.pitch_spread) for _ in range(p.variants)]


def write_wav(path: Path, samples: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(struct.pack(f"<{len(samples)}h", *samples))
