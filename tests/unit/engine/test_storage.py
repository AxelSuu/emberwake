from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from emberwake.engine.core.serde import VersionedCodec
from emberwake.engine.platform.documents import load_document, save_document
from emberwake.engine.platform.storage import FileStorage, MemoryStorage, Storage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(params=["memory", "file"])
def storage(request: pytest.FixtureRequest, tmp_path: Path) -> Storage:
    return MemoryStorage() if request.param == "memory" else FileStorage(tmp_path)


def test_read_write_delete(storage: Storage):
    assert storage.read("a.json") is None
    storage.write("a.json", "one")
    storage.write("nested/b.txt", "two")
    assert storage.read("a.json") == "one"
    assert storage.read("nested/b.txt") == "two"
    storage.delete("a.json")
    storage.delete("a.json")
    assert storage.read("a.json") is None


@pytest.mark.parametrize("key", ["", "/abs", "../escape", "a/../../b", "win\\path"])
def test_rejects_unsafe_keys(storage: Storage, key: str):
    with pytest.raises(ValueError, match="invalid storage key"):
        storage.write(key, "x")


def test_file_storage_keeps_backup_and_falls_back_to_it(tmp_path: Path):
    storage = FileStorage(tmp_path)
    storage.write("save.json", "v1")
    storage.write("save.json", "v2")
    assert (tmp_path / "save.json.bak").read_text() == "v1"
    (tmp_path / "save.json").unlink()
    assert storage.read("save.json") == "v1"
    assert not list(tmp_path.glob("*.tmp"))


@dataclass
class Doc:
    value: int = 0


CODEC = VersionedCodec(Doc, version=1)


def test_document_round_trip(storage: Storage):
    save_document(storage, "doc.json", CODEC, Doc(5))
    assert load_document(storage, "doc.json", CODEC, Doc) == Doc(5)


def test_missing_document_uses_default(storage: Storage):
    assert load_document(storage, "doc.json", CODEC, Doc) == Doc()


@pytest.mark.parametrize("text", ["{not json", '{"version": 1, "data": {"value": "x"}}'])
def test_corrupt_document_is_preserved_and_default_used(storage: Storage, text: str):
    storage.write("doc.json", text)
    assert load_document(storage, "doc.json", CODEC, Doc) == Doc()
    assert storage.read("doc.json.corrupt") == text
