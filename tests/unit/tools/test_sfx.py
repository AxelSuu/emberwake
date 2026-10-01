from __future__ import annotations

import wave
from itertools import pairwise
from typing import TYPE_CHECKING

import pytest
from tools.sfx.__main__ import main
from tools.sfx.build import build, build_file
from tools.sfx.synth import RATE, Params, SfxError, from_table, render, variant_pitches

if TYPE_CHECKING:
    from pathlib import Path

PRESET = """
[blip]
wave = "square"
freq = 600.0
variants = 2
"""


def test_length_follows_envelope() -> None:
    p = Params(attack=0.0, sustain=0.1, decay=0.1)
    assert len(render(p)) == round(0.2 * RATE)


def test_render_is_deterministic_and_bounded() -> None:
    p = Params(wave="noise", volume=1.0)
    assert render(p, seed=3) == render(p, seed=3)
    assert render(p, seed=3) != render(p, seed=4)
    assert max(map(abs, render(p, seed=3))) <= 32767


def test_envelope_fades_out() -> None:
    samples = render(Params(wave="sine", attack=0.0, sustain=0.0, decay=0.05, volume=1.0))
    assert abs(samples[-1]) < abs(max(samples, key=abs)) * 0.1


@pytest.mark.parametrize("wave_name", ["square", "saw", "sine", "triangle", "noise"])
def test_every_wave_makes_sound(wave_name: str) -> None:
    assert any(render(Params(wave=wave_name)))


def test_pitch_shift_changes_zero_crossings() -> None:
    def crossings(pitch: float) -> int:
        s = render(Params(wave="sine", sustain=0.2), pitch=pitch)
        return sum(a < 0 <= b for a, b in pairwise(s))

    assert crossings(1.0) > crossings(0.0) * 1.8


def test_variant_pitches_are_stable_and_bounded() -> None:
    p = Params(variants=4, pitch_spread=0.1)
    a = variant_pitches("x/y", p)
    assert a == variant_pitches("x/y", p)
    assert a[0] == 0.0
    assert len(a) == 5
    assert all(abs(v) <= 0.1 for v in a)


@pytest.mark.parametrize(
    "table",
    [
        {"wave": "bogus"},
        {"freq": 0},
        {"volume": 2},
        {"nope": 1},
        {"attack": 0, "sustain": 0, "decay": 0},
    ],
)
def test_invalid_params(table: dict) -> None:
    with pytest.raises(SfxError):
        from_table(table)


def test_build_file_writes_variants(tmp_path: Path) -> None:
    source = tmp_path / "ui.toml"
    source.write_text(PRESET)
    written = build_file(source, tmp_path / "out")
    assert [p.name for p in written] == ["blip.wav", "blip_1.wav", "blip_2.wav"]
    with wave.open(str(written[0])) as f:
        assert (f.getnchannels(), f.getsampwidth(), f.getframerate()) == (1, 2, RATE)


def test_build_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "ui.toml"
    source.write_text(PRESET)
    first = [p.read_bytes() for p in build_file(source, tmp_path / "a")]
    second = [p.read_bytes() for p in build_file(source, tmp_path / "b")]
    assert first == second


def test_build_reports_bad_presets(tmp_path: Path) -> None:
    (tmp_path / "bad.toml").write_text('[x]\nwave = "nope"\n')
    messages: list[str] = []
    assert build(tmp_path, tmp_path / "out", messages.append) == 1
    assert "bad.toml" in messages[0]


def test_cli_builds_repo_presets(tmp_path: Path) -> None:
    assert main(["--out", str(tmp_path)]) == 0
    assert (tmp_path / "player" / "jump.wav").exists()
    assert (tmp_path / "player" / "jump_3.wav").exists()
