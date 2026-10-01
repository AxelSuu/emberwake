"""Wires engine services and game content together and runs the game."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame

from emberwake import __version__
from emberwake.cli import parse_args
from emberwake.engine.audio import Audio
from emberwake.engine.core.events import EventBus
from emberwake.engine.core.log import configure_logging
from emberwake.engine.debug.overlay import DebugOverlay
from emberwake.engine.input.replay import REPLAY_CODEC, Replay
from emberwake.engine.platform.display import Display
from emberwake.engine.platform.documents import load_document, save_document
from emberwake.engine.platform.storage import FileStorage, default_storage
from emberwake.engine.runner import Runner
from emberwake.engine.scene import SceneManager
from emberwake.game import paths
from emberwake.game.achievements import Achievements, load_defs
from emberwake.game.context import GameContext
from emberwake.game.data.settings import SETTINGS_CODEC, SETTINGS_KEY, Settings
from emberwake.game.scenes.boot import BootScene
from emberwake.game.scenes.gameplay import DEFAULT_ROOM, GameplayScene
from emberwake.game.strings import load_strings

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

ORG = "emberwake"
APP = "emberwake"
CANVAS_SIZE = (640, 360)


async def main(argv: Sequence[str] | None = None) -> None:
    """Start the game and run until the player quits."""
    options = parse_args(argv)
    pygame.init()
    storage = default_storage(ORG, APP)
    log_dir = storage.root / "logs" if isinstance(storage, FileStorage) else None
    configure_logging(options.log_level, log_dir)
    log.info("Emberwake %s, pygame-ce %s", __version__, pygame.version.ver)

    settings = load_document(storage, SETTINGS_KEY, SETTINGS_CODEC, Settings)
    display = Display(
        CANVAS_SIZE,
        "Emberwake",
        fullscreen=options.fullscreen or settings.video.fullscreen,
        vsync=settings.video.vsync,
    )
    ctx = GameContext(
        storage=storage,
        settings=settings,
        bus=EventBus(),
        canvas_size=CANVAS_SIZE,
        dev=options.dev,
        strings=load_strings(settings.language, warn=options.dev),
        audio=Audio(paths.sounds(), settings.audio),
        achievements=Achievements.load(load_defs(paths.content("achievements.toml")), storage),
        slot=options.slot,
        new_game=options.new,
        flags=options.flags,
    )
    scenes = SceneManager()
    if options.replay:
        replay = load_document(storage, options.replay, REPLAY_CODEC, Replay)
        scenes.push(GameplayScene(ctx, room=replay.start or DEFAULT_ROOM, replay=replay))
    elif options.room:
        scenes.push(GameplayScene(ctx, room=options.room))
    else:
        scenes.push(BootScene(ctx))
    runner = Runner(
        display,
        scenes,
        fps_cap=settings.video.fps_cap,
        overlay=DebugOverlay() if options.dev else None,
        max_frames=options.frames,
        on_frame=ctx.audio.update,
    )
    try:
        await runner.run()
    finally:
        scenes.close()
        ctx.achievements.save()
        save_document(storage, SETTINGS_KEY, SETTINGS_CODEC, settings)
        pygame.quit()
