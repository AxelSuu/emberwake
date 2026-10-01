from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest
from tools.sheet.__main__ import sheets
from tools.sheet.render import contact_sheet

if TYPE_CHECKING:
    from pathlib import Path

SKETCH = """
[palette]
o = "#2e222f"
f = "#fb6b1d"
[layers]
a = '''
.o.
ofo
'''
b = '''
.o.
off
'''
[[frames]]
layers = ["a"]
[[frames]]
layers = ["b"]
"""


@pytest.fixture(autouse=True)
def display():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.display.quit()


def test_each_sketch_is_a_row_and_more_frames_make_it_wider(tmp_path: Path) -> None:
    one = tmp_path / "one.pxl"
    one.write_text(SKETCH.split("[[frames]]", maxsplit=1)[0])
    two = tmp_path / "two.pxl"
    two.write_text(SKETCH)
    assert contact_sheet([one], 1).get_height() < contact_sheet([one, two], 1).get_height()


def test_a_broken_sketch_shows_its_error_instead_of_failing(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pxl"
    bad.write_text("[layers]\na = 'x'\n")
    assert contact_sheet([bad], 1).get_width() > 0


def test_sheets_writes_one_png_per_folder(tmp_path: Path) -> None:
    for name in ("rat", "lamp"):
        (tmp_path / "lab" / name).mkdir(parents=True)
        (tmp_path / "lab" / name / "a.pxl").write_text(SKETCH)
    written = sheets(tmp_path / "lab", tmp_path / "out", 2)
    assert sorted(path.name for path in written) == ["lamp.png", "rat.png"]


def test_a_tileset_is_shown_as_terrain(tmp_path: Path) -> None:
    rows = ["oooo" * 4] * 4
    tiles = tmp_path / "ground.pxl"
    tiles.write_text('[palette]\no = "#2e222f"\n[layers]\na = """\n' + "\n".join(rows) + '\n"""\n')
    terrain_width = 20 * 4
    assert contact_sheet([tiles], 1).get_width() >= 3 * terrain_width
