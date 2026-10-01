"""Playing the world: input, player, rooms, camera, juice, placeholder rendering and dev tools."""

from __future__ import annotations

import logging
import time
import tomllib
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.jobs import Jobs
from emberwake.engine.core.serde import SerdeError
from emberwake.engine.debug.time_control import TimeControl
from emberwake.engine.ecs import World
from emberwake.engine.ecs.prefabs import Prefab, load_prefabs
from emberwake.engine.input import InputMapper, InputState
from emberwake.engine.input.replay import REPLAY_CODEC, Replay, ReplayPlayer, ReplayRecorder
from emberwake.engine.physics import Body, Tile, TileSource
from emberwake.engine.platform.documents import save_document
from emberwake.engine.render.camera import Camera
from emberwake.engine.render.chunks import ChunkLayer
from emberwake.engine.scene import Scene
from emberwake.engine.world.ldtk import load_project
from emberwake.engine.world.rooms import Room, RoomEntered, RoomGraph, RoomStreamer, WorldGrid
from emberwake.engine.world.spawning import Spawner, WorldState
from emberwake.game import palette, paths
from emberwake.game.actions import Action
from emberwake.game.components import Sprite
from emberwake.game.feel import Feel, diff, load_feel
from emberwake.game.interact import Interactable, Switch
from emberwake.game.player.controller import Dashed, Died, Jumped, Landed, Motor, new_player
from emberwake.game.player.visual import PlayerVisual
from emberwake.game.render.placeholder import EntityArt, LanternGlow, PlayerSprite, tile_painter
from emberwake.game.schedule import gameplay_schedule
from emberwake.game.signals import Receiver, Wiring

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from emberwake.game.context import GameContext

log = logging.getLogger(__name__)

WORLD = "world.ldtk"
FEEL = "feel.toml"
PREFABS = "prefabs.toml"
COLLISIONS = {1: Tile.SOLID, 2: Tile.ONE_WAY, 3: Tile.HAZARD}
DEFAULT_ROOM = "Test_Room"
BAKE_BUDGET = 0.002
"""Seconds per frame spent baking room art in the background."""
DEBUG_RED = pygame.Color("#e83b3b")
WIRE_ON = pygame.Color("#1ebc73")
WIRE_OFF = pygame.Color("#b33831")


class GameplayScene(Scene):
    def __init__(
        self,
        ctx: GameContext,
        *,
        room: str = DEFAULT_ROOM,
        replay: Replay | None = None,
        world_path: Path | None = None,
    ) -> None:
        self.ctx = ctx
        self.world_path = world_path or paths.levels(WORLD)
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
        self.art = EntityArt()
        self.time = TimeControl()
        self.hitstop = 0
        self.respawn_in = 0
        self.clock = 0.0
        self.show_colliders = False
        self.show_rooms = False
        self.free_camera = False
        self._unsubscribe: list[Callable[[], None]] = []
        self.jobs = Jobs()
        self.layers: dict[str, tuple[ChunkLayer, Iterator[None]]] = {}
        self.world = World()
        self.spawner = Spawner(self.world, self._read_prefabs() or {}, WorldState())
        self.grid = WorldGrid()
        levels = load_project(self.world_path).all_levels
        self.wiring = Wiring.from_levels(levels, self.spawner.prefabs)
        self.rooms = RoomStreamer(
            RoomGraph(levels),
            self.grid,
            "Collisions",
            COLLISIONS,
            on_load=self._room_loaded,
            on_unload=self._room_unloaded,
        )
        self.rooms.enter(room)
        self.spawn_point = self._entry_point(room)
        self.camera.bounds = self.rooms.graph.rects[room]
        self.world.insert_resource(self.actions)
        self.world.insert_resource(ctx.bus)
        self.world.insert_resource(self.grid, key=TileSource)
        self.world.insert_resource(self.grid)
        self.world.insert_resource(self.wiring)
        self.world.insert_resource(self.rooms)
        self.world.insert_resource(self.spawner)
        self.world.insert_resource(self.feel.player)
        self.world.insert_resource(self.feel.rooms)
        self.schedule = gameplay_schedule()
        self.player = self.world.spawn(*self._new_player())
        self.world.flush()
        self.camera.snap(*self._camera_target())

    @property
    def room(self) -> str:
        """The active room."""
        assert self.rooms.active is not None
        return self.rooms.active

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
            bus.subscribe(RoomEntered, self._on_room_entered),
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

    def _read_prefabs(self) -> dict[str, Prefab] | None:
        try:
            return load_prefabs(paths.content(PREFABS))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", PREFABS, error)
            return None

    def _room_loaded(self, room: Room) -> None:
        layer = ChunkLayer(room.rect.topleft, room.rect.size, tile_painter(room.grid))
        job = layer.bake()
        self.layers[room.name] = (layer, job)
        self.jobs.add(job)
        self.spawner.spawn_room(room)

    def _room_unloaded(self, room: Room) -> None:
        self.spawner.despawn_room(room)
        _, job = self.layers.pop(room.name)
        self.jobs.cancel(job)

    def _entry_point(
        self, room: str, near: tuple[float, float] | None = None
    ) -> tuple[float, float]:
        """The room's PlayerStart nearest to `near` (feet, world px), or `near` if it has none."""
        level = self.rooms.graph.levels[room]
        starts = [
            (level.world_x + start.px[0], level.world_y + start.px[1])
            for start in level.entities("PlayerStart")
        ]
        if near is None:
            rect = self.rooms.graph.rects[room]
            return starts[0] if starts else (rect.centerx, rect.centery)
        if not starts:
            return near
        return min(starts, key=lambda p: (p[0] - near[0]) ** 2 + (p[1] - near[1]) ** 2)

    def _new_player(self) -> tuple[Body, Motor]:
        return new_player(*self.spawn_point, self.feel.player)

    def reload(self) -> None:
        """Re-read feel.toml, prefabs and the levels, keeping the player where it is."""
        feel = self._read_feel()
        if feel is not None:
            for key, (old, new) in sorted(diff(self.feel, feel).items()):
                log.info("feel %s: %s -> %s", key, old, new)
            self.feel = feel
            self.world.insert_resource(feel.player)
            self.world.insert_resource(feel.rooms)
            self.camera.retune(feel.camera)
        prefabs = self._read_prefabs()
        if prefabs is not None:
            self.spawner.prefabs = prefabs
        try:
            levels = load_project(self.world_path).all_levels
            graph = RoomGraph(levels)
            if self.room not in graph.levels:
                raise KeyError(self.room)
        except (OSError, KeyError, SerdeError, ValueError) as error:
            log.error("Could not reload %s: %s", self.world_path.name, error)
        else:
            self.wiring = Wiring.from_levels(levels, self.spawner.prefabs)
            self.world.insert_resource(self.wiring)
            self.rooms.reload(graph)
            self.camera.bounds = graph.rects[self.room]
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
            case pygame.K_F4:
                self.show_rooms = not self.show_rooms
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

    # Rooms

    def _on_room_entered(self, event: RoomEntered) -> None:
        self.camera.glide_to(self.rooms.graph.rects[event.room])
        self.spawn_point = self._entry_point(event.room, (event.x, event.y))
        log.debug("Entered %s from %s", event.room, event.previous)

    # Rendering

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        self.jobs.pump(BAKE_BUDGET)
        canvas.fill(palette.INK)
        ox, oy = self.camera.offset(alpha)
        for layer, _ in self.layers.values():
            layer.draw(canvas, (ox, oy))
        for _, body, sprite in self.world.query(Body, Sprite):
            image = self.art.image(sprite.current, (round(body.width), round(body.height)))
            canvas.blit(image, (round(body.x) - ox, round(body.y) - oy))
        for _, body, interactable in self.world.query(Body, Interactable):
            if interactable.in_range:
                above = (round(body.center_x) - ox, round(body.y) - oy - 3)
                canvas.blit(self.art.prompt, self.art.prompt.get_rect(midbottom=above))
        if self.respawn_in == 0:
            self._draw_player(canvas, ox, oy, alpha)
        if self.show_colliders:
            self._draw_colliders(canvas, ox, oy)
        if self.show_rooms:
            self._draw_rooms(canvas, ox, oy)
            self._draw_wires(canvas, ox, oy)

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

    def _draw_rooms(self, canvas: pygame.Surface, ox: int, oy: int) -> None:
        font = pygame.font.Font(None, 16)
        for name, rect in self.rooms.graph.rects.items():
            if name == self.room:
                color, state = palette.EMBER_HOT, "active"
            elif name in self.layers:
                color, state = palette.MIST, "loaded"
            else:
                color, state = palette.DUSK, "unloaded"
            if name in self.layers:
                layer, _ = self.layers[name]
                state += f" {layer.baked}/{layer.total}"
            pygame.draw.rect(canvas, color, rect.move(-ox, -oy), 1)
            text = font.render(f"{name} ({state})", False, color, "black")
            canvas.blit(text, (rect.x - ox + 3, rect.y - oy + 3))

    def _draw_wires(self, canvas: pygame.Surface, ox: int, oy: int) -> None:
        for _, body, switch in self.world.query(Body, Switch):
            start = (body.center_x - ox, body.y + body.height / 2 - oy)
            for iid in switch.targets:
                eid = self.spawner.resolve(iid)
                target = None if eid is None else self.world.find(eid, Body)
                if target is None:
                    continue
                receiver = self.world.find(eid, Receiver) if eid is not None else None
                color = WIRE_ON if receiver is not None and receiver.powered else WIRE_OFF
                end = (target.center_x - ox, target.y + target.height / 2 - oy)
                pygame.draw.line(canvas, color, start, end)
