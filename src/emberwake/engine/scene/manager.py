"""Stack-based scene manager.

The top scene receives input. Overlays (pause, dialogue) set `blocks_update` / `blocks_draw`
to ``False`` so the scenes beneath keep running or stay visible. Stack changes requested
during a frame are applied at the start of the next `update`, so scenes never see the stack
change under them mid-iteration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable

    import pygame

log = logging.getLogger(__name__)


class Scene:
    """Base class for game states. Override only the hooks you need."""

    blocks_update: ClassVar[bool] = True
    """Scenes below this one do not update while it is on the stack."""
    blocks_draw: ClassVar[bool] = True
    """Scenes below this one are not drawn while it is on the stack."""

    manager: SceneManager

    def on_enter(self) -> None:
        """Called once when pushed onto the stack."""

    def on_exit(self) -> None:
        """Called once when removed from the stack."""

    def on_pause(self) -> None:
        """Called when another scene is pushed on top of this one."""

    def on_resume(self) -> None:
        """Called when this scene becomes the top scene again."""

    def handle(self, event: pygame.Event) -> None:
        """Process one input event. Only the top scene receives events."""

    def update(self, dt: float) -> None:
        """Advance one fixed simulation step of `dt` seconds."""

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        """Render onto `canvas`; `alpha` is the interpolation factor between steps."""


class SceneManager:
    """Owns the scene stack and forwards the frame lifecycle to it."""

    def __init__(self) -> None:
        self._stack: list[Scene] = []
        self._pending: list[Callable[[], None]] = []

    @property
    def top(self) -> Scene | None:
        """The scene receiving input, if any."""
        return self._stack[-1] if self._stack else None

    @property
    def scenes(self) -> tuple[Scene, ...]:
        """The stack, bottom first."""
        return tuple(self._stack)

    def __bool__(self) -> bool:
        return bool(self._stack or self._pending)

    def push(self, scene: Scene) -> None:
        """Put `scene` on top of the stack."""
        self._pending.append(lambda: self._push(scene))

    def pop(self) -> None:
        """Remove the top scene."""
        self._pending.append(self._pop)

    def replace(self, scene: Scene) -> None:
        """Swap the top scene for `scene`."""
        self._pending.append(lambda: self._replace(scene))

    def switch(self, scene: Scene) -> None:
        """Clear the whole stack and start `scene`."""
        self._pending.append(lambda: self._switch(scene))

    def close(self) -> None:
        """Exit every scene, top first, dropping queued changes (on quit)."""
        self._pending.clear()
        while self._stack:
            self._pop(resume=False)

    def apply_pending(self) -> None:
        """Apply queued stack changes. Called automatically by `update`."""
        while self._pending:
            pending, self._pending = self._pending, []
            for change in pending:
                change()

    def handle(self, event: pygame.Event) -> None:
        """Forward `event` to the top scene."""
        if self._stack:
            self._stack[-1].handle(event)

    def update(self, dt: float) -> None:
        """Apply stack changes, then update every scene not blocked by one above it."""
        self.apply_pending()
        for scene in reversed(self._stack):
            scene.update(dt)
            if scene.blocks_update:
                break

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        """Draw visible scenes bottom to top."""
        first = 0
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index].blocks_draw:
                first = index
                break
        for scene in self._stack[first:]:
            scene.draw(canvas, alpha)

    def _push(self, scene: Scene) -> None:
        if self._stack:
            self._stack[-1].on_pause()
        scene.manager = self
        self._stack.append(scene)
        log.debug("Enter %s", type(scene).__name__)
        scene.on_enter()

    def _pop(self, *, resume: bool = True) -> None:
        if not self._stack:
            return
        scene = self._stack.pop()
        log.debug("Exit %s", type(scene).__name__)
        scene.on_exit()
        if resume and self._stack:
            self._stack[-1].on_resume()

    def _replace(self, scene: Scene) -> None:
        self._pop(resume=False)
        self._push(scene)

    def _switch(self, scene: Scene) -> None:
        while self._stack:
            self._pop(resume=False)
        self._push(scene)
