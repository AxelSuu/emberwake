from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from emberwake.engine.core.i18n import Strings, flatten, load_tables

if TYPE_CHECKING:
    from pathlib import Path

TABLES = {
    "en": {"hi": "Hello {name}", "only_en": "English", "plain": "Plain"},
    "sv": {"hi": "Hej {name}", "plain": "Enkel"},
}


def test_looks_up_the_current_language_and_fills_placeholders():
    strings = Strings(TABLES, "sv")
    assert strings.t("hi", name="Ada") == "Hej Ada"
    strings.language = "en"
    assert strings.t("hi", name="Ada") == "Hello Ada"
    assert strings.languages == ["en", "sv"]


def test_falls_back_to_english_then_to_the_key(caplog: pytest.LogCaptureFixture):
    strings = Strings(TABLES, "sv", warn=True)
    assert strings.t("only_en") == "English"
    with caplog.at_level(logging.WARNING):
        assert strings.t("nope") == "nope"
        strings.t("nope")
    assert strings.missing == {"nope"}
    assert [r.message for r in caplog.records].count("Missing string nope") == 1


def test_unknown_languages_use_the_fallback_and_missing_is_quiet_unless_asked(
    caplog: pytest.LogCaptureFixture,
):
    strings = Strings(TABLES, "de")
    with caplog.at_level(logging.WARNING):
        assert strings.t("plain") == "Plain"
        assert strings.t("nope") == "nope"
    assert caplog.records == []


def test_a_missing_placeholder_value_keeps_the_text(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING):
        assert Strings(TABLES).t("hi") == "Hello {name}"
    assert "needs values" in caplog.text


def test_nested_tables_become_dotted_keys_and_files_load_by_name(tmp_path: Path):
    (tmp_path / "en.toml").write_text('[menu]\nplay = "Play"\n[menu.sub]\nx = "X"\n')
    assert load_tables(tmp_path) == {"en": {"menu.play": "Play", "menu.sub.x": "X"}}
    with pytest.raises(ValueError, match="must be text"):
        flatten({"a": 1})
