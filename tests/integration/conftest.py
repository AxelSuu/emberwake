from __future__ import annotations

import pygame
import pytest

from emberwake.app import CANVAS_SIZE
from emberwake.engine.core.events import EventBus
from emberwake.engine.platform.display import Display
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.game.context import GameContext
from emberwake.game.data.settings import Settings
from emberwake.game.strings import load_strings


@pytest.fixture
def display():
    pygame.init()
    yield Display(CANVAS_SIZE, "test", vsync=False)
    pygame.quit()


@pytest.fixture
def ctx(display: Display) -> GameContext:
    return GameContext(
        MemoryStorage(), Settings(), EventBus(), CANVAS_SIZE, dev=True, strings=load_strings("en")
    )
