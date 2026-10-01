"""String tables and lookup: every player-facing string goes through `Strings.t`.

Tables are TOML files named after the language (``en.toml``, ``sv.toml``); nested tables become
dotted keys, so ``[menu]`` with ``play = "Play"`` is ``menu.play``. A key missing in the current
language falls back to the fallback language, then to the key itself.

Example:
    >>> strings = Strings({"en": {"hi": "Hello {name}"}, "sv": {}}, "sv")
    >>> strings.t("hi", name="Ada")
    'Hello Ada'
"""

from __future__ import annotations

import logging
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)


def flatten(data: dict[str, object], prefix: str = "") -> dict[str, str]:
    """Nested tables to dotted keys. Raises `ValueError` for anything but strings and tables."""
    flat: dict[str, str] = {}
    for key, value in data.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{name}."))
        elif isinstance(value, str):
            flat[name] = value
        else:
            msg = f"{name}: strings must be text, not {type(value).__name__}"
            raise ValueError(msg)
    return flat


def load_tables(directory: Path) -> dict[str, dict[str, str]]:
    """Read every ``<language>.toml`` in `directory`."""
    return {
        path.stem: flatten(tomllib.loads(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.toml"))
    }


class Strings:
    """Looks keys up in the current language.

    Attributes:
        language: The current language code; unknown languages fall back.
        missing: Keys that were asked for and found nowhere, for `--dev` reports and tests.
    """

    def __init__(
        self,
        tables: dict[str, dict[str, str]] | None = None,
        language: str = "en",
        fallback: str = "en",
        *,
        warn: bool = False,
    ) -> None:
        self.tables = tables or {}
        self.language = language
        self.fallback = fallback
        self.warn = warn
        self.missing: set[str] = set()

    @property
    def languages(self) -> list[str]:
        """Language codes that have a table."""
        return sorted(self.tables)

    def t(self, key: str, **values: object) -> str:
        """The text for `key` with `{placeholders}` filled from `values`."""
        text = self.tables.get(self.language, {}).get(key)
        if text is None:
            text = self.tables.get(self.fallback, {}).get(key)
        if text is None:
            if key not in self.missing:
                self.missing.add(key)
                log.log(logging.WARNING if self.warn else logging.DEBUG, "Missing string %s", key)
            return key
        try:
            return text.format(**values)
        except (KeyError, IndexError):
            log.warning("String %s needs values it was not given: %r", key, text)
            return text
