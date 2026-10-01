from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame
import pytest
from tools.atlas.__main__ import main
from tools.atlas.pack import AtlasError, entries, layout, pack

if TYPE_CHECKING:
    from pathlib import Path


def sprite(path: Path, size: tuple[int, int], color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    pygame.image.save(surface, path)


@pytest.fixture
def assets(tmp_path: Path) -> Path:
    root = tmp_path / "assets"
    sprite(root / "props/torch.png", (8, 16), (255, 0, 0, 255))
    sprite(root / "props/torch_n.png", (8, 16), (10, 20, 30, 255))
    sprite(root / "props/torch_e.png", (8, 16), (255, 255, 0, 255))
    sprite(root / "player.png", (12, 12), (0, 255, 0, 255))
    return root


def test_entries_group_channels(assets: Path) -> None:
    found = {e.name: e for e in entries(assets)}
    assert sorted(found) == ["player", "props/torch"]
    assert found["props/torch"].normal is not None
    assert found["player"].emissive is None


def test_layout_has_no_overlaps_and_is_order_independent() -> None:
    sizes = [(f"s{i}", (10 + i, 8 + i % 3)) for i in range(20)]
    first, size = layout(sizes, 64, 1)
    second, _ = layout(sizes[::-1], 64, 1)
    assert first == second
    rects = [(*first[n], *s) for n, s in sizes]
    for i, (x, y, w, h) in enumerate(rects):
        assert x + w <= size[0]
        assert y + h <= size[1]
        for ox, oy, ow, oh in rects[i + 1 :]:
            assert x + w <= ox or ox + ow <= x or y + h <= oy or oy + oh <= y


def test_too_wide_sprite_raises() -> None:
    with pytest.raises(AtlasError):
        layout([("big", (100, 4))], 64, 1)


def test_channels_share_rects(assets: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    manifest = pack(assets, out)
    torch = manifest["sprites"]["props/torch"]
    point = (torch["x"] + 1, torch["y"] + 1)
    assert tuple(pygame.image.load(out / "atlas.png").get_at(point)) == (255, 0, 0, 255)
    assert tuple(pygame.image.load(out / "atlas_n.png").get_at(point)) == (10, 20, 30, 255)
    assert tuple(pygame.image.load(out / "atlas_e.png").get_at(point)) == (255, 255, 0, 255)
    player = manifest["sprites"]["player"]
    at = (player["x"], player["y"])
    assert tuple(pygame.image.load(out / "atlas_n.png").get_at(at)) == (128, 128, 255, 255)
    assert tuple(pygame.image.load(out / "atlas_e.png").get_at(at)) == (0, 0, 0, 255)


def test_output_is_deterministic(assets: Path, tmp_path: Path) -> None:
    pack(assets, tmp_path / "a")
    pack(assets, tmp_path / "b")
    for name in ("atlas.png", "atlas_n.png", "atlas_e.png", "atlas.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_manifest_json(assets: Path, tmp_path: Path) -> None:
    pack(assets, tmp_path / "out")
    data = json.loads((tmp_path / "out" / "atlas.json").read_text())
    assert set(data["sprites"]) == {"player", "props/torch"}
    assert data["size"][0] == 512


def test_mismatched_channel_size_raises(assets: Path, tmp_path: Path) -> None:
    sprite(assets / "player_n.png", (4, 4), (0, 0, 0, 255))
    with pytest.raises(AtlasError):
        pack(assets, tmp_path / "out")


def test_cli(assets: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--assets", str(assets), "--out", str(tmp_path / "o")]) == 0
    assert "2 sprites" in capsys.readouterr().out
