from __future__ import annotations

import tomllib
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from emberwake.engine.core.serde import SerdeError
from emberwake.game import paths
from emberwake.game.feel import Feel, diff, load_feel

if TYPE_CHECKING:
    from pathlib import Path


def test_feel_toml_matches_code_defaults():
    assert load_feel(paths.content("feel.toml")) == Feel()


def test_diff_lists_changed_values():
    old = Feel()
    new = replace(old, player=replace(old.player, max_run=200))
    assert diff(old, new) == {"player.max_run": (180.0, 200.0)}


def test_bad_values_raise_with_path(tmp_path: Path):
    path = tmp_path / "feel.toml"
    path.write_text("[player]\nmax_run = 'fast'\n")
    with pytest.raises(SerdeError, match=r"\$\.player\.max_run"):
        load_feel(path)
    path.write_text("[player\n")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_feel(path)
