from __future__ import annotations

from typing import Any

from emberwake.engine.core.serde import to_data
from emberwake.game.data.settings import SETTINGS_CODEC, Settings


def test_round_trip():
    settings = Settings()
    assert SETTINGS_CODEC.load(SETTINGS_CODEC.dump(settings)) == settings


def test_v1_controls_gain_interact_bindings():
    v1: Any = to_data(Settings())
    del v1["controls"]["keys"]["interact"]
    v1["controls"]["keys"]["jump"] = ["j"]
    loaded = SETTINGS_CODEC.load({"version": 1, "data": v1})
    assert loaded.controls.keys["interact"] == ["up", "w", "e"]
    assert loaded.controls.keys["jump"] == ["j"]


def test_v4_gamepad_bindings_are_dropped():
    v4: Any = to_data(Settings())
    v4["controls"]["buttons"] = {"jump": ["a"]}
    loaded = SETTINGS_CODEC.load({"version": 4, "data": v4})
    assert loaded == Settings()
    dumped: Any = to_data(loaded)
    assert "buttons" not in dumped["controls"]


def test_v1_without_controls_gets_defaults():
    loaded = SETTINGS_CODEC.load({"version": 1, "data": {"language": "sv"}})
    assert loaded.controls == Settings().controls
    assert loaded.language == "sv"


def test_v3_settings_load_with_default_accessibility():
    raw = {"version": 3, "data": {"language": "sv", "video": {"crt": True}}}
    loaded = SETTINGS_CODEC.load(raw)
    assert (loaded.language, loaded.video.crt) == ("sv", True)
    assert loaded.accessibility.reduce_flashes is False
