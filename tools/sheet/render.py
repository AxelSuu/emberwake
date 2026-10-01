"""Lay sprites out as a contact sheet: every frame on a dark, a lit and a mid-tone panel.

The lit panel goes through the game's own software backend with a lantern-colored light, so a
sketch is judged the way it will be seen: mostly in the dark, near a warm light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from tools.pxl.build import render
from tools.pxl.spec import PxlError, parse

from emberwake.engine.render.frame import Flag, RenderFrame
from emberwake.engine.render.software import SoftwareBackend

if TYPE_CHECKING:
    from pathlib import Path

DARK = "#2e222f"
GROUND = "#45293f"
MID = "#625565"
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


def panel(frame: pygame.Surface, background: str, *, lit: bool) -> pygame.Surface:
    """`frame` standing on a strip of ground, in the dark or lit from the front."""
    width, height = frame.get_width() + 2 * PAD, frame.get_height() + 2 * PAD
    surface = pygame.Surface((width, height))
    surface.fill(background)
    surface.fill(GROUND, (0, height - PAD, width, PAD))
    if not lit:
        surface.blit(frame, (PAD, PAD))
        return surface
    scene = RenderFrame(flags=Flag.LIGHTING)
    scene.sprite(frame, PAD, PAD)
    scene.light(width * 0.75, height * 0.55, max(width, height), LIGHT, 1.0)
    SoftwareBackend().render(scene, surface)
    return surface


def variant(path: Path, font: pygame.font.Font) -> pygame.Surface:
    """One row: the file's name, then each frame on the three panels."""
    try:
        images = frames(path)
    except PxlError as error:
        message = font.render(str(error)[-90:], False, ERROR)
        row = pygame.Surface((message.get_width() + 2 * PAD, LABEL + PAD))
        row.blit(message, (PAD, 2))
        return row
    panels = [
        [panel(image, DARK, lit=False), panel(image, DARK, lit=True), panel(image, MID, lit=False)]
        for image in images
    ]
    cell_w = sum(p.get_width() for p in panels[0]) + PAD
    cell_h = panels[0][0].get_height()
    row = pygame.Surface((max(cell_w * len(panels), 120) + PAD, cell_h + LABEL + PAD))
    row.fill(DARK)
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
    sheet.fill(DARK)
    y = 0
    for row in rows:
        sheet.blit(row, (0, y))
        y += row.get_height()
    return pygame.transform.scale_by(sheet, scale)
