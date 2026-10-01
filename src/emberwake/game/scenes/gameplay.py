"""Playing a room: input, player, camera, juice, placeholder rendering and dev tools."""

from __future__ import annotations

import logging
import time
import tomllib
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.serde import SerdeError
from emberwake.engine.debug.time_control import TimeControl
from emberwake.engine.ecs import World
from emberwake.engine.input import InputMapper, InputState
from emberwake.engine.input.replay import REPLAY_CODEC, Replay, ReplayPlayer, ReplayRecorder
from emberwake.engine.physics import Body, Tile
from emberwake.engine.platform.documents import save_document
from emberwake.engine.render.camera import Camera
from emberwake.engine.scene import Scene
from emberwake.engine.world.ldtk import load_project
from emberwake.game import palette, paths
from emberwake.game.actions import Action
from emberwake.game.feel import Feel, diff, load_feel
from emberwake.game.player.controller import Dashed, Died, Jumped, Landed, Motor, new_player
from emberwake.game.player.visual import PlayerVisual
from emberwake.game.render.placeholder import LanternGlow, PlayerSprite, bake_room
from emberwake.game.schedule import gameplay_schedule

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.game.context import GameContext

log = logging.getLogger(__name__)

WORLD = "world.ldtk"
FEEL = "feel.toml"
COLLISIONS = {1: Tile.SOLID, 2: Tile.ONE_WAY, 3: Tile.HAZARD}
DEFAULT_ROOM = "Test_Room"
DEBUG_RED = pygame.Color("#e83b3b")


class GameplayScene(Scene):
    def __init__(
        self, ctx: GameContext, *, room: str = DEFAULT_ROOM, replay: Replay | None = None
    ) -> None:
        self.ctx = ctx
        self.room = room
        self.feel = self._read_feel() or Feel()
        self.mapper = InputMapper(Action, ctx.settings.controls)
        self.replay = ReplayPlayer(replay, Action) if replay else None
        self.actions = InputState[Action]()
        self.recorder = ReplayRecorder[Action](room)
        self.camera = Camera(ctx.canvas_size, self.feel.camera)
        self.camera.shake.intensity = ctx.settings.video.screen_shake
        self.visual = PlayerVisual()
        self.sprite = PlayerSprite()
        self.glow = LanternGlow()
        self.time = TimeControl()
        self.hitstop = 0
        self.respawn_in = 0
        self.clock = 0.0
        self.show_colliders = False
        self.free_camera = False
        self._unsubscribe: list[Callable[[], None]] = []
        self.world = World()
        self.world.insert_resource(self.actions)
        self.world.insert_resource(ctx.bus)
        self.world.insert_resource(self.feel.player)
        self.schedule = gameplay_schedule()
        self._load_room()
        self.player = self.world.spawn(*self._new_player())
        self.world.flush()
        self.camera.snap(*self._camera_target())

    @property
    def body(self) -> Body:
        return self.world.get(self.player, Body)

    @property
    def motor(self) -> Motor:
        return self.world.get(self.player, Motor)

    # Lifecycle

    def on_enter(self) -> None:
        bus = self.ctx.bus
        self._unsubscribe = [
            bus.subscribe(Jumped, self._on_jumped),
            bus.subscribe(Landed, self._on_landed),
            bus.subscribe(Dashed, self._on_dashed),
            bus.subscribe(Died, self._on_died),
        ]

    def on_exit(self) -> None:
        for unsubscribe in self._unsubscribe:
            unsubscribe()

    # Loading

    def _read_feel(self) -> Feel | None:
        try:
            return load_feel(paths.content(FEEL))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", FEEL, error)
            return None

    def _load_room(self) -> None:
        level = load_project(paths.levels(WORLD)).level(self.room)
        self.grid = level.layer("Collisions").to_tile_grid(COLLISIONS)
        self.world.insert_resource(self.grid)
        starts = level.entities("PlayerStart")
        self.spawn_point = starts[0].px if starts else (level.width // 2, level.height // 2)
        self.room_image = bake_room(self.grid)
        self.camera.bounds = pygame.Rect(0, 0, level.width, level.height)

    def _new_player(self) -> tuple[Body, Motor]:
        return new_player(*self.spawn_point, self.feel.player)

    def reload(self) -> None:
        """Re-read feel.toml and the level, keeping the player where it is."""
        feel = self._read_feel()
        if feel is not None:
            for key, (old, new) in sorted(diff(self.feel, feel).items()):
                log.info("feel %s: %s -> %s", key, old, new)
            self.feel = feel
            self.world.insert_resource(feel.player)
            self.camera.retune(feel.camera)
        try:
            self._load_room()
        except (OSError, KeyError, SerdeError, ValueError) as error:
            log.error("Could not reload room %s: %s", self.room, error)
        log.info("Reloaded")

    # Input

    def handle(self, event: pygame.Event) -> None:
        self.mapper.handle(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                from emberwake.game.scenes.title import TitleScene  # noqa: PLC0415

                self.manager.replace(TitleScene(self.ctx))
            elif self.ctx.dev:
                self._dev_key(event.key)
        elif event.type == pygame.MOUSEMOTION and self.free_camera and event.buttons[0]:
            self.camera.x -= event.rel[0]
            self.camera.y -= event.rel[1]
            self.camera.previous = (self.camera.x, self.camera.y)

    def _dev_key(self, key: int) -> None:
        match key:
            case pygame.K_F2:
                self.show_colliders = not self.show_colliders
            case pygame.K_F3:
                self.free_camera = not self.free_camera
            case pygame.K_F5:
                self.reload()
            case pygame.K_F9:
                self.save_replay()
            case pygame.K_p:
                self.time.toggle_pause()
            case pygame.K_PERIOD:
                self.time.step()
            case pygame.K_COMMA:
                self.time.toggle_slow()

    def save_replay(self) -> str:
        key = f"replays/{time.strftime('%Y%m%d-%H%M%S')}.json"
        save_document(self.ctx.storage, key, REPLAY_CODEC, self.recorder.replay)
        log.info("Saved replay %s (%d ticks)", key, self.recorder.replay.ticks)
        return key

    def _sample(self) -> frozenset[Action]:
        if self.replay is not None:
            if not self.replay.finished:
                frame = self.replay.sample()
                if not self.replay.finished:
                    return frame
            log.info("Replay finished, live input")
            self.replay = None
        return self.mapper.sample()

    # Simulation

    def update(self, dt: float) -> None:
        if not self.time.should_tick():
            return
        self.clock += dt
        juice = self.feel.juice
        self.visual.update(juice.squash_recovery, dt)
        if self.hitstop > 0:
            self.hitstop -= 1
            self.camera.shake.update(dt)
            return

        frame = self._sample()
        self.actions.advance(frame)
        self.recorder.record(frame)
        if self.respawn_in > 0:
            self.respawn_in -= 1
            if self.respawn_in == 0:
                self.world.add(self.player, *self._new_player())
        self.schedule.run(self.world, dt)
        if not self.free_camera:
            self.camera.update(*self._camera_target(), self.motor.facing, dt)

    def _camera_target(self) -> tuple[float, float]:
        body = self.body
        return body.center_x, body.y + body.height / 2

    # Juice

    def _on_jumped(self, event: Jumped) -> None:
        self.visual.stretch(self.feel.juice.stretch)
        if event.wall:
            self.camera.shake.add(self.feel.juice.wall_jump_trauma)

    def _on_landed(self, event: Landed) -> None:
        juice, max_fall = self.feel.juice, self.feel.player.max_fall
        impact = min(event.speed / max_fall, 1.0)
        self.visual.squash(juice.squash * impact)
        if impact >= juice.hard_landing:
            self.camera.shake.add(juice.hard_landing_trauma)

    def _on_dashed(self, _: Dashed) -> None:
        self.hitstop = max(self.hitstop, self.feel.juice.dash_hitstop)
        self.camera.shake.add(self.feel.juice.dash_trauma)

    def _on_died(self, _: Died) -> None:
        juice = self.feel.juice
        self.hitstop = max(self.hitstop, juice.death_hitstop)
        self.camera.shake.add(juice.death_trauma)
        self.respawn_in = juice.respawn_delay

    # Rendering

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        canvas.fill(palette.INK)
        ox, oy = self.camera.offset(alpha)
        canvas.blit(self.room_image, (-ox, -oy))
        if self.respawn_in == 0:
            self._draw_player(canvas, ox, oy, alpha)
        if self.show_colliders:
            self._draw_colliders(canvas, ox, oy)

    def _draw_player(self, canvas: pygame.Surface, ox: int, oy: int, alpha: float) -> None:
        p, body, visual = self.motor, self.body, self.visual
        px, py = p.previous
        x = px + (body.x - px) * alpha
        y = py + (body.y - py) * alpha
        feet = (x + body.width / 2 - ox, y + body.height - oy)
        lx, ly = self.sprite.lantern_offset(p.facing, visual.scale_x, visual.scale_y)
        self.glow.draw(canvas, (feet[0] + lx, feet[1] + ly), self.clock)
        image = self.sprite.image(p.facing, visual.scale_x, visual.scale_y)
        canvas.blit(image, image.get_rect(midbottom=(round(feet[0]), round(feet[1]))))

    def _draw_colliders(self, canvas: pygame.Surface, ox: int, oy: int) -> None:
        p, body = self.motor, self.body
        rect = pygame.Rect(
            round(body.x) - ox, round(body.y) - oy, round(body.width), round(body.height)
        )
        pygame.draw.rect(canvas, DEBUG_RED, rect, 1)
        font = pygame.font.Font(None, 16)
        lines = [
            f"{p.state.value} grounded={p.grounded} one_way={p.on_one_way}",
            f"v=({p.vx:6.1f}, {p.vy:6.1f}) air={min(p.air_ticks, 99)} dash={p.dash_charges}",
            f"hitstop={self.hitstop} paused={self.time.paused} slow={self.time.slow}",
        ]
        for i, line in enumerate(lines):
            text = font.render(line, False, "white", "black")
            canvas.blit(text, (canvas.get_width() - text.get_width() - 2, 2 + i * 12))
