"""Load and save versioned JSON documents through a `Storage`."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import SerdeError

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.core.serde import VersionedCodec
    from emberwake.engine.platform.storage import Storage

log = logging.getLogger(__name__)


def load_document[T, D](
    storage: Storage, key: str, codec: VersionedCodec[T], default: Callable[[], D]
) -> T | D:
    """Load `key`, or return ``default()`` if it is missing or unreadable.

    Unreadable documents are logged and preserved under ``<key>.corrupt`` so a bad save is
    never silently lost.
    """
    text = storage.read(key)
    if text is None:
        return default()
    try:
        return codec.load(json.loads(text))
    except (json.JSONDecodeError, SerdeError) as error:
        log.error("Could not load %s (%s); using defaults", key, error)
        storage.write(key + ".corrupt", text)
        return default()


def save_document[T](storage: Storage, key: str, codec: VersionedCodec[T], obj: T) -> None:
    """Serialize `obj` with `codec` and store it under `key`."""
    storage.write(key, json.dumps(codec.dump(obj), indent=2, ensure_ascii=False) + "\n")
