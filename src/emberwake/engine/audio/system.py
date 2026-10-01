"""The audio system: an SFX bank with variants, music stems with fades, and ducking.

It never raises for missing files or a missing audio device; it logs and goes quiet, so a
machine without sound (or the dummy test driver) still runs the game.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Protocol

import pygame

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)

EXTENSIONS = (".ogg", ".wav")
STEM_FADE = 1.5
DUCK_ATTACK = 0.1
DUCK_RELEASE = 0.8


class Levels(Protocol):
    """Volume settings, each 0 to 1. The game's audio settings fit this."""

    master: float
    music: float
    sfx: float


def approach(value: float, target: float, step: float) -> float:
    """Move `value` toward `target` by at most `step`."""
    if value < target:
        return min(value + step, target)
    return max(value - step, target)


class Audio:
    """Plays sound effects by name and a set of looping music stems whose levels fade.

    Files live under `root`. ``sfx("player/jump")`` plays ``player/jump.wav`` or one of its
    variants ``player/jump_1.wav``, ``player/jump_2.wav`` and so on, chosen with a seeded
    generator. Stems are looped together from one start, so they stay in time, and are
    silenced or brought in by `set_stems`.

    Args:
        root: Directory holding sounds, or ``None`` for a silent system.
        levels: Live volume settings, read on every update so changes apply at once.
        seed: Seed for variant choice.
    """

    def __init__(
        self, root: Path | None = None, levels: Levels | None = None, seed: int = 0
    ) -> None:
        self.root = root
        self.levels = levels
        self.rng = random.Random(seed)
        self.enabled = root is not None and self._init_mixer()
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        self._variants: dict[str, list[str]] = {}
        self._stems: dict[str, pygame.mixer.Sound] = {}
        self._channels: dict[str, pygame.mixer.Channel] = {}
        self._level: dict[str, float] = {}
        self._target: dict[str, float] = {}
        self._duck = 1.0
        self._duck_hold = 0.0
        self._duck_floor = 1.0

    @staticmethod
    def _init_mixer() -> bool:
        if pygame.mixer.get_init():
            return True
        try:
            pygame.mixer.init()
        except pygame.error:
            log.warning("No audio device; running silent")
            return False
        return True

    @property
    def music_gain(self) -> float:
        """Current gain for music from the settings and ducking."""
        return self._volume("music") * self._duck

    def sfx(self, name: str, volume: float = 1.0) -> pygame.mixer.Sound | None:
        """Play `name` (or a random variant of it); return the sound, or ``None`` if silent."""
        if not self.enabled:
            return None
        key = self._pick(name)
        sound = self._load(key)
        if sound is None:
            return None
        sound.set_volume(max(0.0, min(volume, 1.0)) * self._volume("sfx"))
        sound.play()
        return sound

    def start_music(self, stems: list[str], levels: dict[str, float] | None = None) -> None:
        """Begin looping `stems` together, each at its starting level (default silent)."""
        self.stop_music()
        if not self.enabled:
            return
        for name in stems:
            sound = self._load(name)
            if sound is None:
                continue
            self._stems[name] = sound
            self._level[name] = self._target[name] = (levels or {}).get(name, 0.0)
        for name, sound in self._stems.items():
            channel = sound.play(loops=-1)
            if channel is not None:
                self._channels[name] = channel
        self._apply()

    def set_stems(self, levels: dict[str, float]) -> None:
        """Fade each named stem toward a level from 0 to 1; unnamed stems are left alone."""
        for name, level in levels.items():
            if name in self._stems:
                self._target[name] = max(0.0, min(level, 1.0))

    def stop_music(self) -> None:
        """Stop and forget every stem."""
        for sound in self._stems.values():
            sound.stop()
        self._stems.clear()
        self._channels.clear()
        self._level.clear()
        self._target.clear()

    def duck(self, amount: float = 0.5, hold: float = 0.4) -> None:
        """Pull music down by `amount` (0 to 1) for `hold` seconds, then ease it back."""
        self._duck_floor = min(self._duck_floor if self._duck_hold > 0 else 1.0, 1.0 - amount)
        self._duck_hold = max(self._duck_hold, hold)

    def update(self, dt: float) -> None:
        """Fade stems, release ducking and track the volume settings."""
        if not self.enabled:
            return
        for name, target in self._target.items():
            self._level[name] = approach(self._level[name], target, dt / STEM_FADE)
        if self._duck_hold > 0:
            self._duck_hold -= dt
            self._duck = approach(self._duck, self._duck_floor, dt / DUCK_ATTACK)
        else:
            self._duck = approach(self._duck, 1.0, dt / DUCK_RELEASE)
        self._apply()

    def stem_level(self, name: str) -> float:
        """The faded level of stem `name`, before settings and ducking."""
        return self._level.get(name, 0.0)

    def _apply(self) -> None:
        gain = self.music_gain
        for name, channel in self._channels.items():
            channel.set_volume(self._level[name] * gain)

    def _volume(self, kind: str) -> float:
        if self.levels is None:
            return 1.0
        return max(0.0, min(self.levels.master * getattr(self.levels, kind), 1.0))

    def _pick(self, name: str) -> str:
        variants = self._variants.get(name)
        if variants is None:
            variants = [name] if self._find(name) else []
            index = 1
            while self._find(f"{name}_{index}"):
                variants.append(f"{name}_{index}")
                index += 1
            self._variants[name] = variants
        return self.rng.choice(variants) if variants else name

    def _find(self, name: str) -> Path | None:
        assert self.root is not None
        for extension in EXTENSIONS:
            path = self.root / f"{name}{extension}"
            if path.is_file():
                return path
        return None

    def _load(self, name: str) -> pygame.mixer.Sound | None:
        if name not in self._sounds:
            path = self._find(name)
            sound = None
            if path is None:
                log.warning("No sound %s", name)
            else:
                try:
                    sound = pygame.mixer.Sound(path)
                except pygame.error:
                    log.exception("Could not load %s", path)
            self._sounds[name] = sound
        return self._sounds[name]
