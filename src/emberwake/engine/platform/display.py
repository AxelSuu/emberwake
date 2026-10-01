"""The game window: a fixed-size pixel canvas scaled up by SDL on the GPU."""

from __future__ import annotations

import logging

import pygame

log = logging.getLogger(__name__)


class Display:
    """Owns the window and the low-resolution canvas scenes draw on.

    Uses ``pygame.SCALED`` so upscaling is done by the SDL renderer (nearest neighbour,
    letterboxed) and mouse coordinates arrive already in canvas space.
    """

    def __init__(
        self, size: tuple[int, int], title: str, *, fullscreen: bool = False, vsync: bool = True
    ) -> None:
        pygame.display.set_caption(title)
        flags = pygame.SCALED | pygame.RESIZABLE | (pygame.FULLSCREEN if fullscreen else 0)
        try:
            self.canvas = pygame.display.set_mode(size, flags, vsync=int(vsync))
        except pygame.error:
            log.warning("VSync unavailable, falling back to an uncapped swap")
            self.canvas = pygame.display.set_mode(size, flags)

    @property
    def size(self) -> tuple[int, int]:
        """Canvas size in pixels."""
        return self.canvas.get_size()

    def toggle_fullscreen(self) -> None:
        """Switch between windowed and fullscreen."""
        pygame.display.toggle_fullscreen()

    def present(self) -> None:
        """Show the finished frame."""
        pygame.display.flip()
