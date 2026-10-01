"""Frame statistics overlay."""

from __future__ import annotations

from collections import deque

import pygame


class DebugOverlay:
    """Shows fps and a frame-time graph in the top-left corner. Toggle with `toggle`."""

    GRAPH_SIZE = (120, 30)
    BUDGET_MS = 1000 / 60

    def __init__(self, *, visible: bool = True) -> None:
        self.visible = visible
        self._font = pygame.font.Font(None, 16)
        self._frame_ms: deque[float] = deque(maxlen=self.GRAPH_SIZE[0])

    def toggle(self) -> None:
        """Show or hide the overlay."""
        self.visible = not self.visible

    def record(self, frame_ms: float) -> None:
        """Record the duration of the last frame."""
        self._frame_ms.append(frame_ms)

    def draw(self, canvas: pygame.Surface, fps: float) -> None:
        """Draw onto `canvas` if visible."""
        if not self.visible:
            return
        width, height = self.GRAPH_SIZE
        text = self._font.render(f"{fps:5.1f} fps", False, "white", "black")
        canvas.blit(text, (2, 2))
        graph = pygame.Rect(2, 4 + text.get_height(), width, height)
        canvas.fill((0, 0, 0), graph)
        scale = height / (self.BUDGET_MS * 2)
        budget_y = graph.bottom - self.BUDGET_MS * scale
        pygame.draw.line(canvas, (80, 80, 80), (graph.left, budget_y), (graph.right, budget_y))
        for i, ms in enumerate(self._frame_ms):
            bar = min(ms * scale, height)
            color = (30, 188, 115) if ms <= self.BUDGET_MS else (232, 59, 59)
            x = graph.left + i
            pygame.draw.line(canvas, color, (x, graph.bottom - bar), (x, graph.bottom - 1))
