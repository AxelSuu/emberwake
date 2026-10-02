from __future__ import annotations

import pytest

from emberwake.cli import Options, parse_args


def test_defaults():
    assert parse_args(None) == Options()


def test_slot_and_new_game():
    options = parse_args(["--slot", "2", "--new"])
    assert (options.slot, options.new) == (2, True)
    with pytest.raises(SystemExit):
        parse_args(["--slot", "4"])


def test_flags_parse_names_and_values():
    assert parse_args(["--flags", "met_tinker, up_hp=2"]).flags == {"met_tinker": 1, "up_hp": 2}
    with pytest.raises(SystemExit):
        parse_args(["--flags", "up_hp=many"])
