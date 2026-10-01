from __future__ import annotations

from typing import Any

from emberwake.engine.core.serde import to_data
from emberwake.game.data.settings import SETTINGS_CODEC, Settings


def test_round_trip():
    settings = Settings()
    assert SETTINGS_CODEC.load(SETTINGS_CODEC.dump(settings)) == settings


def test_v1_controls_gain_interact_bindings():
    v1: Any = to_data(Settings())
    del v1["controls"]["keys"]["interact"], v1["controls"]["buttons"]["interact"]
    v1["controls"]["keys"]["jump"] = ["j"]
    loaded = SETTINGS_CODEC.load({"version": 1, "data": v1})
    assert loaded.controls.keys["interact"] == ["up", "w", "e"]
    assert loaded.controls.buttons["interact"] == ["y", "dpad_up"]
    assert loaded.controls.keys["jump"] == ["j"]


def test_v1_without_controls_gets_defaults():
    loaded = SETTINGS_CODEC.load({"version": 1, "data": {"language": "sv"}})
    assert loaded.controls == Settings().controls
    assert loaded.language == "sv"
