from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pygame
from tools.palette.__main__ import main
from tools.palette.lint import lint

if TYPE_CHECKING:
    import pytest

INK = "#2e222f"


def write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_on_palette_text_passes_and_case_does_not_matter(tmp_path: Path):
    write(tmp_path, "content/a.toml", f'color = "{INK}"\nother = "#FBFF86"\n')
    assert lint(tmp_path) == []


def test_off_palette_text_is_reported_with_its_line(tmp_path: Path):
    write(tmp_path, "src/emberwake/game/x.py", f'A = "{INK}"\nB = "#123456"\n')
    (offender,) = lint(tmp_path)
    assert (offender.where, offender.color) == ("2", "#123456")
    assert "x.py:2: #123456" in str(offender)


def test_engine_code_and_other_places_are_not_scanned(tmp_path: Path):
    write(tmp_path, "src/emberwake/engine/x.py", 'A = "#123456"\n')
    write(tmp_path, "docs/x.md", "#123456")
    assert lint(tmp_path) == []


def test_png_pixels_are_checked_unless_transparent(tmp_path: Path):
    image = pygame.Surface((3, 1), pygame.SRCALPHA)
    image.set_at((0, 0), pygame.Color(INK))
    image.set_at((1, 0), (1, 2, 3, 255))
    image.set_at((2, 0), (9, 9, 9, 0))
    (tmp_path / "assets").mkdir()
    pygame.image.save(image, tmp_path / "assets/a.png")
    (offender,) = lint(tmp_path)
    assert (offender.where, offender.color) == ("1,0", "#010203")


def test_the_repository_is_clean():
    assert lint(Path(__file__).parents[3]) == []


def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["lint", "--root", str(tmp_path)]) == 0
    write(tmp_path, "content/a.toml", 'c = "#000001"')
    assert main(["lint", "--root", str(tmp_path)]) == 1
    assert "#000001" in capsys.readouterr().err
