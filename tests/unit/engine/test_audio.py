from __future__ import annotations

import struct
import wave
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame
import pytest

from emberwake.engine.audio import Audio

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@dataclass
class Volumes:
    master: float = 1.0
    music: float = 1.0
    sfx: float = 1.0


def tone(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(22050)
        f.writeframes(struct.pack("<2205h", *([8000, -8000] * 1102 + [0])))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for name in ("jump", "jump_1", "jump_2", "drums", "pads"):
        tone(tmp_path / f"{name}.wav")
    return tmp_path


@pytest.fixture(autouse=True)
def mixer() -> Iterator[None]:
    pygame.mixer.init(frequency=22050)
    yield
    pygame.mixer.quit()


def test_silent_without_a_directory() -> None:
    audio = Audio()
    assert not audio.enabled
    assert audio.sfx("jump") is None
    audio.update(0.1)


def test_missing_sound_is_quiet(root: Path) -> None:
    assert Audio(root).sfx("nope") is None


def test_variants_are_all_used_and_seeded(root: Path) -> None:
    def picks(seed: int) -> list[object]:
        audio = Audio(root, seed=seed)
        return [audio.sfx("jump") for _ in range(30)]

    first = picks(1)
    assert len({id(s) for s in first}) == 3
    assert len({id(s) for s in picks(1)}) == 3


def test_sfx_volume_follows_settings(root: Path) -> None:
    levels = Volumes(master=0.5, sfx=0.5)
    sound = Audio(root, levels).sfx("drums", 0.8)
    assert sound is not None
    assert sound.get_volume() == pytest.approx(0.2, abs=0.01)
    levels.master = 0.0
    quiet = Audio(root, levels).sfx("drums")
    assert quiet is not None
    assert quiet.get_volume() == 0.0


def test_stems_start_silent_and_fade_in(root: Path) -> None:
    audio = Audio(root)
    audio.start_music(["drums", "pads"], {"drums": 1.0})
    assert audio.stem_level("pads") == 0.0
    audio.set_stems({"pads": 1.0})
    for _ in range(30):
        audio.update(0.1)
    assert audio.stem_level("pads") == 1.0
    audio.set_stems({"pads": 0.0})
    audio.update(0.3)
    assert 0.0 < audio.stem_level("pads") < 1.0


def test_music_follows_the_volume_settings_live(root: Path) -> None:
    levels = Volumes(music=1.0)
    audio = Audio(root, levels)
    audio.start_music(["drums"], {"drums": 1.0})
    levels.music = 0.25
    audio.update(0.016)
    assert audio.music_gain == pytest.approx(0.25)
    assert audio._channels["drums"].get_volume() == pytest.approx(0.25, abs=0.01)


def test_ducking_dips_then_recovers(root: Path) -> None:
    audio = Audio(root)
    audio.start_music(["drums"], {"drums": 1.0})
    audio.duck(0.6, hold=0.3)
    for _ in range(4):
        audio.update(0.05)
    assert audio.music_gain == pytest.approx(0.4, abs=0.01)
    for _ in range(40):
        audio.update(0.05)
    assert audio.music_gain == pytest.approx(1.0)


def test_stop_music_forgets_stems(root: Path) -> None:
    audio = Audio(root)
    audio.start_music(["drums"])
    audio.stop_music()
    assert audio.stem_level("drums") == 0.0
