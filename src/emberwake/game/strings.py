"""The game's string tables, loaded from content/strings."""

from __future__ import annotations

import logging
import tomllib

from emberwake.engine.core.i18n import Strings, load_tables
from emberwake.game import paths

log = logging.getLogger(__name__)


def load_strings(language: str, *, warn: bool = False) -> Strings:
    """Tables for every language, set to `language`; `warn` reports missing keys (`--dev`)."""
    try:
        tables = load_tables(paths.content("strings"))
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        log.error("Could not load strings: %s", error)
        tables = {}
    return Strings(tables, language, warn=warn)
