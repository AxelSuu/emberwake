"""Key/value text storage for settings, saves and records.

Keys are relative slash-separated paths such as ``"settings.json"`` or ``"ghosts/trial1.rpl"``.
Desktop stores files under the per-user preference directory; the browser build stores them in
``localStorage``.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Protocol

from emberwake.engine.platform import IS_WEB

log = logging.getLogger(__name__)

BACKUP_SUFFIX = ".bak"


class Storage(Protocol):
    """Minimal text storage interface."""

    def read(self, key: str) -> str | None:
        """Return the stored text, or ``None`` if `key` does not exist."""
        ...

    def write(self, key: str, text: str) -> None:
        """Store `text` under `key`, replacing any previous value."""
        ...

    def delete(self, key: str) -> None:
        """Remove `key` if present."""
        ...


def validate_key(key: str) -> PurePosixPath:
    """Reject keys that are empty, absolute or escape the storage root."""
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts or "\\" in key:
        msg = f"invalid storage key {key!r}"
        raise ValueError(msg)
    return path


class MemoryStorage:
    """In-memory storage for tests and as a last-resort fallback."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def read(self, key: str) -> str | None:
        """See `Storage.read`."""
        validate_key(key)
        return self.data.get(key)

    def write(self, key: str, text: str) -> None:
        """See `Storage.write`."""
        validate_key(key)
        self.data[key] = text

    def delete(self, key: str) -> None:
        """See `Storage.delete`."""
        self.data.pop(key, None)


class FileStorage:
    """Files under a root directory, written atomically with one backup generation.

    A write never leaves a half-written file: text goes to a temporary file that replaces the
    target in one step. The previous version is kept as ``<key>.bak`` and `read` falls back to
    it if the main file is missing.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root.joinpath(*validate_key(key).parts)

    def read(self, key: str) -> str | None:
        """See `Storage.read`."""
        path = self._path(key)
        for candidate in (path, path.with_name(path.name + BACKUP_SUFFIX)):
            try:
                return candidate.read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
        return None

    def write(self, key: str, text: str) -> None:
        """See `Storage.write`."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + BACKUP_SUFFIX))
        tmp.replace(path)

    def delete(self, key: str) -> None:
        """See `Storage.delete`. Also removes the backup."""
        path = self._path(key)
        path.unlink(missing_ok=True)
        path.with_name(path.name + BACKUP_SUFFIX).unlink(missing_ok=True)


class WebStorage:
    """Browser ``localStorage`` (pygbag only)."""

    def __init__(self, prefix: str) -> None:
        import platform as pygbag_platform  # noqa: PLC0415

        # pygbag replaces the stdlib `platform` module with a browser bridge.
        self._local = pygbag_platform.window.localStorage  # ty: ignore[unresolved-attribute]
        self._prefix = prefix

    def read(self, key: str) -> str | None:
        """See `Storage.read`."""
        return self._local.getItem(self._prefix + str(validate_key(key)))

    def write(self, key: str, text: str) -> None:
        """See `Storage.write`."""
        self._local.setItem(self._prefix + str(validate_key(key)), text)

    def delete(self, key: str) -> None:
        """See `Storage.delete`."""
        self._local.removeItem(self._prefix + str(validate_key(key)))


def default_storage(org: str, app: str) -> Storage:
    """Pick the right storage for the current platform."""
    if IS_WEB:
        return WebStorage(prefix=f"{org}.{app}/")
    import pygame  # noqa: PLC0415

    try:
        return FileStorage(Path(pygame.system.get_pref_path(org, app)))
    except pygame.error:
        log.exception("No writable preference directory, progress will not be saved")
        return MemoryStorage()
