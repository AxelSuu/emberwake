from __future__ import annotations

import re
from pathlib import Path

from emberwake.engine.core.i18n import load_tables
from emberwake.game import paths

TABLES = load_tables(paths.content("strings"))
SOURCE = Path(__file__).parents[3] / "src/emberwake/game"
CALL = re.compile(r"""\bt\(\s*["']([a-z0-9_.]+)["']""")


def test_every_language_defines_the_same_keys_as_english():
    english = set(TABLES["en"])
    for language, table in TABLES.items():
        assert set(table) == english, language


def test_every_key_the_game_asks_for_exists_and_is_used():
    sources = [path.read_text(encoding="utf-8") for path in SOURCE.rglob("*.py")]
    used = {key for text in sources for key in CALL.findall(text)}
    assert used <= set(TABLES["en"])
    assert set(TABLES["en"]) <= used


def test_placeholders_match_across_languages():
    names = re.compile(r"{(\w+)}")
    for key, text in TABLES["en"].items():
        for language, table in TABLES.items():
            assert set(names.findall(table[key])) == set(names.findall(text)), (language, key)
