"""Player settings, persisted as ``settings.json``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emberwake.engine.core.serde import VersionedCodec
from emberwake.engine.input import Bindings
from emberwake.game.actions import FLARE_KEYS, INTERACT_KEYS, default_bindings

SETTINGS_KEY = "settings.json"


@dataclass(slots=True)
class VideoSettings:
    fullscreen: bool = False
    vsync: bool = True
    fps_cap: int = 0
    screen_shake: float = 1.0
    bloom: bool = True
    grading: bool = True
    vignette: bool = True
    crt: bool = False
    shadows: bool = True
    light_shafts: bool = True


@dataclass(slots=True)
class AudioSettings:
    master: float = 1.0
    music: float = 0.8
    sfx: float = 0.8


@dataclass(slots=True)
class AccessibilitySettings:
    reduce_flashes: bool = False


@dataclass(slots=True)
class Settings:
    video: VideoSettings = field(default_factory=VideoSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    controls: Bindings = field(default_factory=default_bindings)
    language: str = "en"


def _add_interact(data: dict[str, Any]) -> dict[str, Any]:
    """v1 -> v2: bind the new interact action in saved controls."""
    controls = data.get("controls", {})
    if "keys" in controls:
        controls["keys"].setdefault("interact", list(INTERACT_KEYS))
    return data


def _add_post_effects(data: dict[str, Any]) -> dict[str, Any]:
    """v2 -> v3: video effect toggles; missing ones take their defaults on load."""
    return data


def _add_accessibility(data: dict[str, Any]) -> dict[str, Any]:
    """v3 -> v4: the accessibility group; missing fields take their defaults on load."""
    return data


def _add_flare(data: dict[str, Any]) -> dict[str, Any]:
    """v5 -> v6: bind the new flare action in saved controls."""
    keys = data.get("controls", {}).get("keys")
    if keys is not None:
        keys.setdefault("flare", list(FLARE_KEYS))
    return data


def _drop_gamepad(data: dict[str, Any]) -> dict[str, Any]:
    """v4 -> v5: gamepad support was removed, so saved button bindings go."""
    data.get("controls", {}).pop("buttons", None)
    return data


SETTINGS_CODEC = VersionedCodec(
    Settings,
    version=6,
    migrations={
        1: _add_interact,
        2: _add_post_effects,
        3: _add_accessibility,
        4: _drop_gamepad,
        5: _add_flare,
    },
)
