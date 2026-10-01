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
