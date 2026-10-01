"""Pack sprite PNGs into albedo, normal and emissive atlases that share one layout."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pygame

NORMAL_SUFFIX = "_n"
EMISSIVE_SUFFIX = "_e"
FLAT_NORMAL = (128, 128, 255, 255)
BLACK = (0, 0, 0, 255)
CLEAR = (0, 0, 0, 0)


class AtlasError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    albedo: Path
    normal: Path | None
    emissive: Path | None


def entries(root: Path) -> list[Entry]:
    """Sprites under `root`, named by relative path without extension; sorted for determinism."""
    paths = {p.relative_to(root).with_suffix("").as_posix(): p for p in root.glob("**/*.png")}
    found = []
    for name, path in sorted(paths.items()):
        if name.endswith((NORMAL_SUFFIX, EMISSIVE_SUFFIX)) and name[:-2] in paths:
            continue
        found.append(
            Entry(name, path, paths.get(name + NORMAL_SUFFIX), paths.get(name + EMISSIVE_SUFFIX))
        )
    return found


def layout(
    sizes: list[tuple[str, tuple[int, int]]], width: int, padding: int
) -> tuple[dict[str, tuple[int, int]], tuple[int, int]]:
    """Shelf-pack `sizes` (tallest first, ties by name) into rows `width` wide.

    Returns each name's position and the final atlas size.
    """
    order = sorted(sizes, key=lambda item: (-item[1][1], item[0]))
    positions: dict[str, tuple[int, int]] = {}
    x = y = row_height = used = 0
    for name, (w, h) in order:
        if w + padding > width:
            raise AtlasError(f"{name} ({w}px wide) does not fit a {width}px atlas")
        if x + w + padding > width:
            x, y, row_height = 0, y + row_height, 0
        positions[name] = (x + padding, y + padding)
        x += w + padding
        row_height = max(row_height, h + padding)
        used = max(used, y + row_height)
    return positions, (width, used + padding if positions else 0)


def load(path: Path) -> pygame.Surface:
    image = pygame.image.load(path)
    surface = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    surface.blit(image, (0, 0))
    return surface


def pack(root: Path, out: Path, *, name: str = "atlas", width: int = 512, padding: int = 1) -> dict:
    """Write ``<name>.png``, ``<name>_n.png``, ``<name>_e.png`` and ``<name>.json`` into `out`.

    The three images are laid out identically, so one rect addresses a sprite in all of them.
    """
    found = entries(root)
    albedo = {entry.name: load(entry.albedo) for entry in found}
    positions, size = layout([(n, s.get_size()) for n, s in albedo.items()], width, padding)

    sheets = {
        "": pygame.Surface(size, pygame.SRCALPHA),
        NORMAL_SUFFIX: pygame.Surface(size, pygame.SRCALPHA),
        EMISSIVE_SUFFIX: pygame.Surface(size, pygame.SRCALPHA),
    }
    sheets[""].fill(CLEAR)
    sheets[NORMAL_SUFFIX].fill(CLEAR)
    sheets[EMISSIVE_SUFFIX].fill(CLEAR)

    sprites = {}
    for entry in found:
        image = albedo[entry.name]
        w, h = image.get_size()
        x, y = positions[entry.name]
        sprites[entry.name] = {"x": x, "y": y, "w": w, "h": h}
        sheets[""].blit(image, (x, y))
        for suffix, path, fill in (
            (NORMAL_SUFFIX, entry.normal, FLAT_NORMAL),
            (EMISSIVE_SUFFIX, entry.emissive, BLACK),
        ):
            layer = pygame.Surface((w, h), pygame.SRCALPHA)
            layer.fill(fill)
            if path is not None:
                other = load(path)
                if other.get_size() != (w, h):
                    raise AtlasError(f"{path} is {other.get_size()}, expected {(w, h)}")
                layer = other
            sheets[suffix].blit(layer, (x, y))

    out.mkdir(parents=True, exist_ok=True)
    for suffix, sheet in sheets.items():
        pygame.image.save(sheet, out / f"{name}{suffix}.png")
    manifest = {"size": list(size), "sprites": sprites}
    (out / f"{name}.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest
