from __future__ import annotations

import re
from pathlib import Path

from emberwake.engine.core.i18n import load_tables
from emberwake.game import paths

TABLES = load_tables(paths.content("strings"))
SOURCE = Path(__file__).parents[3] / "src/emberwake/game"
DYNAMIC = ("area.", "achievement.", "skin.", "lantern.", "shop.", "dialogue.", "trial.", "grant.")
"""Key families the game builds at runtime (``f"achievement.{id}.name"``)."""
CALL = re.compile(r"""\bt\(\s*["']([a-z0-9_.]+)["']""")


def test_every_language_defines_the_same_keys_as_english():
    english = set(TABLES["en"])
    for language, table in TABLES.items():
        assert set(table) == english, language


def test_every_key_the_game_asks_for_exists_and_is_used():
    sources = [path.read_text(encoding="utf-8") for path in SOURCE.rglob("*.py")]
    used = {key for text in sources for key in CALL.findall(text)}
    assert used <= set(TABLES["en"])
    quoted = {
        key
        for key in TABLES["en"]
        if key.startswith(DYNAMIC) or any(f'"{key}"' in text for text in sources)
    }
    assert quoted == set(TABLES["en"])


def test_placeholders_match_across_languages():
    names = re.compile(r"{(\w+)}")
    for key, text in TABLES["en"].items():
        for language, table in TABLES.items():
            assert set(names.findall(table[key])) == set(names.findall(text)), (language, key)
