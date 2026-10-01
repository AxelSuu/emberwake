"""The main loop: variable-rate rendering around a fixed-rate simulation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.clock import FixedStep

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.debug.overlay import DebugOverlay
    from emberwake.engine.platform.display import Display
    from emberwake.engine.scene import SceneManager

log = logging.getLogger(__name__)


class Runner:
    """Runs frames until the scene stack is empty, the window closes or `stop` is called.

    The loop is async and yields every frame so the same code runs in the browser (pygbag),
    where blocking the event loop would freeze the page.
    """

    def __init__(
        self,
        display: Display,
        scenes: SceneManager,
        *,
        step: float = 1 / 60,
        fps_cap: int = 0,
        overlay: DebugOverlay | None = None,
        max_frames: int | None = None,
        on_frame: Callable[[float], None] | None = None,
    ) -> None:
        self.display = display
        self.scenes = scenes
        self.fps_cap = fps_cap
        self.overlay = overlay
        self.max_frames = max_frames
        self.on_frame = on_frame
        self._fixed = FixedStep(step)
        self._running = False

    def stop(self) -> None:
        """Finish the current frame, then return from `run`."""
        self._running = False

    async def run(self) -> None:
        """Run the loop."""
        clock = pygame.Clock()
        self._running = True
        self.scenes.apply_pending()
        frames = 0
        while self._running and self.scenes:
            frame_time = clock.tick(self.fps_cap) / 1000
            for event in pygame.event.get():
                self._dispatch(event)
            if self.on_frame:
                self.on_frame(frame_time)
            for _ in range(self._fixed.advance(frame_time)):
                self.scenes.update(self._fixed.step)
            self.scenes.draw(self.display.canvas, self._fixed.alpha)
            if self.overlay:
                self.overlay.record(clock.get_rawtime())
                self.overlay.draw(self.display.canvas, clock.get_fps())
            self.display.present()
            await asyncio.sleep(0)
            frames += 1
            if self.max_frames is not None and frames >= self.max_frames:
                break
        log.info("Loop finished after %d frames", frames)

    def _dispatch(self, event: pygame.Event) -> None:
        if event.type == pygame.QUIT:
            self.stop()
        elif event.type == pygame.KEYDOWN and (
            event.key == pygame.K_F11
            or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT)
        ):
            self.display.toggle_fullscreen()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and self.overlay:
            self.overlay.toggle()
        else:
            self.scenes.handle(event)
