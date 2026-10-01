from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame
import pytest
from tools.pxl.__main__ import main
from tools.pxl.build import build, compile_file, output_path, watch
from tools.pxl.spec import PxlError, parse

if TYPE_CHECKING:
    from pathlib import Path

SPRITE = """
[palette]
o = "#2e222f"
f = "#fb6b1d"

[layers]
body = '''
.oo.
oooo
'''
flame = '''
.f..
....
'''
"""


def source(tmp_path: Path, text: str = SPRITE, name: str = "props/torch.pxl") -> Path:
    path = tmp_path / "art" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def colors(path: Path) -> list[list[tuple[int, ...]]]:
    image = pygame.image.load(path)
    size = image.get_size()
    return [[tuple(image.get_at((x, y))) for x in range(size[0])] for y in range(size[1])]


def test_layers_stack_bottom_to_top_into_one_png(tmp_path: Path):
    path = source(tmp_path)
    out = compile_file(path, tmp_path / "art", tmp_path / "assets")
    assert out == tmp_path / "assets/props/torch.png"
    rows = colors(out)
    assert rows[0][0][3] == 0
    assert rows[0][1] == (0xFB, 0x6B, 0x1D, 255)
    assert rows[0][2] == (0x2E, 0x22, 0x2F, 255)
    assert not out.with_suffix(".json").exists()


def test_frames_become_a_sheet_with_a_json_of_timings(tmp_path: Path):
    frames = '\n[[frames]]\nlayers = ["body"]\nms = 80\n\n[[frames]]\nlayers = ["body", "flame"]\n'
    text = SPRITE + frames
    out = compile_file(source(tmp_path, text), tmp_path / "art", tmp_path / "assets")
    image = pygame.image.load(out)
    assert image.get_size() == (8, 2)
    assert image.get_at((1, 0))[3] == 255
    assert image.get_at((5, 0)) == (0xFB, 0x6B, 0x1D, 255)
    assert image.get_at((1, 0)) == (0x2E, 0x22, 0x2F, 255)
    info = json.loads(out.with_suffix(".json").read_text())
    assert info == {"frame": [4, 2], "frames": 2, "ms": [80, 100]}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (SPRITE.replace("oooo", "ooo"), "row 2 is 3 wide"),
        (SPRITE.replace("oooo", "ooxo"), "'x' is not in the palette"),
        (SPRITE.replace('"#fb6b1d"', '"orange"'), "not #rrggbb"),
        (SPRITE.replace("f = ", '"." = '), "palette key"),
        (SPRITE + '\n[[frames]]\nlayers = ["nope"]\n', "unknown layer"),
        ("[palette]\no = '#2e222f'\n", "no [layers]"),
        (SPRITE.replace(".f..\n....", ".f.\n..."), "same size"),
        ("not toml [", "Expected"),
    ],
)
def test_bad_sources_say_what_is_wrong(tmp_path: Path, text: str, message: str):
    with pytest.raises(PxlError, match=message.replace("[", r"\[")) as error:
        parse(source(tmp_path, text))
    assert "torch.pxl" in str(error.value)


def test_build_compiles_all_and_counts_failures(tmp_path: Path):
    source(tmp_path)
    source(tmp_path, "[layers]\nx = 'a'\n", "bad.pxl")
    lines: list[str] = []
    assert build(tmp_path / "art", tmp_path / "assets", lines.append) == 1
    assert (tmp_path / "assets/props/torch.png").exists()
    assert any(line.startswith("error:") for line in lines)


def test_watch_recompiles_only_changed_sources(tmp_path: Path):
    path = source(tmp_path)
    lines: list[str] = []
    watch(tmp_path / "art", tmp_path / "assets", lines.append, interval=0, rounds=2)
    assert len(lines) == 1
    path.write_text(SPRITE.replace("f = ", "f = '#f9c22b'\ng = "))
    path.touch()
    watch(tmp_path / "art", tmp_path / "assets", lines.append, interval=0, rounds=1)
    assert len(lines) == 2


def test_output_path_mirrors_the_art_tree(tmp_path: Path):
    art, assets = tmp_path / "art", tmp_path / "assets"
    assert output_path(art / "a/b.pxl", art, assets) == assets / "a/b.png"


def test_cli_build(tmp_path: Path):
    source(tmp_path)
    args = ["build", "--art", str(tmp_path / "art"), "--assets", str(tmp_path / "assets")]
    assert main(args) == 0
    source(tmp_path, "oops", "bad.pxl")
    assert main(args) == 1
