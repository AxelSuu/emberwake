"""Lay sprites out as a contact sheet: every frame in the dark, lantern-lit, and flat.

The first two panels go through the game's own software backend, with a room's darkness and
emissive pixels on the glow layer, so a sketch is judged the way it will be seen: mostly in the
dark (where only what glows shows), and near a warm light. The flat panel shows the colors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from tools.autotile.blob import SOURCE_TILES, build_sheet, tile_for
from tools.pxl.build import render
from tools.pxl.spec import PxlError, parse

from emberwake.engine.render.frame import Flag, Layer, RenderFrame
from emberwake.engine.render.software import SoftwareBackend
from emberwake.game.render.backdrop import DARK
from emberwake.game.render.glow import glow_of

if TYPE_CHECKING:
    from pathlib import Path

BACK = "#2e222f"
DARK_BG = "#625565"
GROUND = "#45293f"
MID = "#7f708a"
TEXT = "#c7dcd0"
ERROR = "#e83b3b"
LIGHT = (249, 194, 43)
PAD = 6
LABEL = 14


def frames(path: Path) -> list[pygame.Surface]:
    """Each frame of the sprite at `path`, one surface per frame."""
    sprite = parse(path)
    sheet = render(sprite)
    width, height = sprite.size
    count = len(sprite.frames)
    return [sheet.subsurface((i * width, 0, width, height)).copy() for i in range(count)]


def panel(frame: pygame.Surface, *, light: float | None) -> pygame.Surface:
    """`frame` standing on a strip of ground, flat or in a dark room.

    `light` None draws it flat; otherwise it stands in the dark, lit by a lantern of that
    intensity (0 for none) to its right.
    """
    width, height = frame.get_width() + 2 * PAD, frame.get_height() + 2 * PAD
    surface = pygame.Surface((width, height))
    surface.fill(DARK_BG if light is not None else MID)
    surface.fill(GROUND, (0, height - PAD, width, PAD))
    if light is None:
        surface.blit(frame, (PAD, PAD))
        return surface
    scene = RenderFrame(flags=Flag.LIGHTING, ambient=DARK)
    scene.sprite(frame, PAD, PAD)
    if (glow := glow_of(frame)) is not None:
        scene.sprite(glow, PAD, PAD, Layer.GLOW)
    if light > 0:
        scene.light(width * 0.8, height * 0.5, max(width, height), LIGHT, light)
    SoftwareBackend().render(scene, surface)
    return surface


TERRAIN = (
    "....................",
    "....................",
    "..........####......",
    "....................",
    "######.......#######",
    "######.......#######",
    "#######.....########",
    "####################",
)
"""A patch of ground with a floating ledge, a pit and a step, for previewing tilesets."""


def is_tileset(sprite: pygame.Surface) -> bool:
    """A row of the autotile source tiles (fill, edge, outer, inner)."""
    width, height = sprite.get_size()
    return width == height * len(SOURCE_TILES)


def terrain(source: pygame.Surface) -> pygame.Surface:
    """The `TERRAIN` patch tiled with the 47-tile set built from `source`."""
    size = source.get_height()
    sheet = build_sheet(source)
    solid = {(x, y) for y, row in enumerate(TERRAIN) for x, c in enumerate(row) if c == "#"}
    out = pygame.Surface((len(TERRAIN[0]) * size, len(TERRAIN) * size), pygame.SRCALPHA)
    for x, y in solid:
        index = tile_for(solid, x, y)
        area = ((index % 8) * size, (index // 8) * size, size, size)
        out.blit(sheet, (x * size, y * size), area)
    return out


def variant(path: Path, font: pygame.font.Font) -> pygame.Surface:
    """One row: the file's name, then each frame on the three panels."""
    try:
        images = frames(path)
    except PxlError as error:
        message = font.render(str(error)[-90:], False, ERROR)
        row = pygame.Surface((message.get_width() + 2 * PAD, LABEL + PAD))
        row.blit(message, (PAD, 2))
        return row
    if is_tileset(images[0]):
        images = [terrain(image) for image in images]
    panels = [
        [panel(image, light=0.0), panel(image, light=1.0), panel(image, light=None)]
        for image in images
    ]
    cell_w = sum(p.get_width() for p in panels[0]) + PAD
    cell_h = panels[0][0].get_height()
    row = pygame.Surface((max(cell_w * len(panels), 120) + PAD, cell_h + LABEL + PAD))
    row.fill(BACK)
    row.blit(font.render(path.stem, False, TEXT), (PAD, 2))
    for index, trio in enumerate(panels):
        x = PAD + index * cell_w
        for image in trio:
            row.blit(image, (x, LABEL))
            x += image.get_width()
    return row


def contact_sheet(paths: list[Path], scale: int = 3) -> pygame.Surface:
    """Every sprite in `paths`, one row each, scaled up by `scale`."""
    pygame.font.init()
    font = pygame.font.Font(None, 14)
    rows = [variant(path, font) for path in paths]
    width = max((row.get_width() for row in rows), default=1)
    height = sum(row.get_height() for row in rows) or 1
    sheet = pygame.Surface((width, height))
    sheet.fill(BACK)
    y = 0
    for row in rows:
        sheet.blit(row, (0, y))
        y += row.get_height()
    return pygame.transform.scale_by(sheet, scale)
