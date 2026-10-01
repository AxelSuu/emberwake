"""Player settings, persisted as ``settings.json``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emberwake.engine.core.serde import VersionedCodec
from emberwake.engine.input import Bindings
from emberwake.game.actions import INTERACT_BUTTONS, INTERACT_KEYS, default_bindings

SETTINGS_KEY = "settings.json"


@dataclass(slots=True)
class VideoSettings:
    fullscreen: bool = False
    vsync: bool = True
    fps_cap: int = 0
    screen_shake: float = 1.0


@dataclass(slots=True)
class AudioSettings:
    master: float = 1.0
    music: float = 0.8
    sfx: float = 0.8


@dataclass(slots=True)
class Settings:
    video: VideoSettings = field(default_factory=VideoSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    controls: Bindings = field(default_factory=default_bindings)
    language: str = "en"


def _add_interact(data: dict[str, Any]) -> dict[str, Any]:
    """v1 -> v2: bind the new interact action in saved controls."""
    controls = data.get("controls", {})
    if "keys" in controls:
        controls["keys"].setdefault("interact", list(INTERACT_KEYS))
    if "buttons" in controls:
        controls["buttons"].setdefault("interact", list(INTERACT_BUTTONS))
    return data


SETTINGS_CODEC = VersionedCodec(Settings, version=2, migrations={1: _add_interact})
