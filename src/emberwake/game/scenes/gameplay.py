"""Playing the world: input, player, rooms, camera, juice, placeholder rendering and dev tools."""

from __future__ import annotations

import functools
import logging
import math
import operator
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
from emberwake.engine.render.frame import Flag, Layer, RenderFrame, ShaftCmd
from emberwake.engine.render.particles import EmitterSpec, ParticleSystem, load_emitters
from emberwake.engine.render.post import PostChain
from emberwake.engine.render.software import SoftwareBackend
from emberwake.engine.scene import Scene
from emberwake.engine.world.ldtk import load_project
from emberwake.engine.world.rooms import Room, RoomEntered, RoomGraph, RoomStreamer, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game import palette, paths
from emberwake.game.actions import Action
from emberwake.game.beacons import Beacon, BeaconLit
from emberwake.game.components import Sprite
from emberwake.game.data.save import SaveSlot, load_slot
from emberwake.game.feel import Feel, diff, load_feel
from emberwake.game.interact import Interactable, Switch
from emberwake.game.player.controller import Dashed, Died, Jumped, Landed, Motor, new_player
from emberwake.game.player.visual import PlayerVisual
from emberwake.game.progress import Progress
from emberwake.game.render.backdrop import Backdrops, BackdropSpec, load_backdrops
from emberwake.game.render.fx import Flash
from emberwake.game.render.placeholder import EntityArt, Flicker, PlayerSprite, tile_painter
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
BACKDROPS = "backdrops.toml"
PARTICLES = "particles.toml"
COLLISIONS = {1: Tile.SOLID, 2: Tile.ONE_WAY, 3: Tile.HAZARD}
DEFAULT_ROOM = "Test_Room"
BAKE_BUDGET = 0.002
"""Seconds per frame spent baking room art in the background."""
GLOW_RADIUS = 64
SHAFT_ANGLES = (-22, 0, 22)
"""Degrees either side of straight up for a lit beacon's light shafts."""
_ember = pygame.Color(palette.EMBER_WARM).lerp(palette.EMBER_HOT, 0.4)
GLOW = (_ember.r, _ember.g, _ember.b)
"""Lantern and beacon light color."""
DEBUG_RED = pygame.Color("#e83b3b")
WIRE_ON = pygame.Color("#1ebc73")
WIRE_OFF = pygame.Color("#b33831")


class GameplayScene(Scene):
    def __init__(
        self,
        ctx: GameContext,
        *,
        room: str | None = None,
        replay: Replay | None = None,
        world_path: Path | None = None,
    ) -> None:
        """Continue from the save slot, or play `room` (or a replay) without loading or saving."""
        self.ctx = ctx
        self.world_path = world_path or paths.levels(WORLD)
        start = self._open_progress(room, replay)
        self.feel = self._read_feel() or Feel()
        self.mapper = InputMapper(Action, ctx.settings.controls)
        self.replay = ReplayPlayer(replay, Action) if replay else None
        self.actions = InputState[Action]()
        self.recorder = ReplayRecorder[Action](start)
        self.camera = Camera(ctx.canvas_size, self.feel.camera)
        self.camera.shake.intensity = ctx.settings.video.screen_shake
        self.visual = PlayerVisual()
        self.sprite = PlayerSprite()
        self.flicker = Flicker()
        self.frame = RenderFrame(flags=self._effects())
        self.post = PostChain(ctx.canvas_size)
        self.backend = SoftwareBackend()
        self.art = EntityArt()
        self.particles = ParticleSystem()
        self.emitters = self._read_emitters() or {}
        self.flash = Flash()
        self.backdrops = Backdrops(self._read_backdrops() or {}, ctx.canvas_size)
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
        self._build_world(start)
        self._show_backdrops()
        self.camera.snap(*self._camera_target())

    def _open_progress(self, room: str | None, replay: Replay | None) -> str:
        """Load the slot unless a room or replay was asked for; return the starting room."""
        ctx = self.ctx
        from_slot = room is None and replay is None
        save = load_slot(ctx.storage, ctx.slot) if from_slot and not ctx.new_game else None
        ctx.new_game = False
        start = room or (save.room if save else DEFAULT_ROOM)
        data = save or SaveSlot(room=start)
        self.progress = Progress(data, ctx.storage, ctx.slot if from_slot else None)
        return start

    def _build_world(self, start: str) -> None:
        self.world = World()
        self.spawner = Spawner(self.world, self._read_prefabs() or {}, self.progress.data.world)
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
        if start not in self.rooms.graph.levels:
            log.warning("No room %s; starting in %s", start, DEFAULT_ROOM)
            start = DEFAULT_ROOM
        self.rooms.enter(start)
        self.progress.discover(self.rooms.graph.levels[start].iid)
        self.spawn_point = self._continue_point(start, self.progress.data.beacon)
        self.camera.bounds = self.rooms.graph.rects[start]
        resources = (self.actions, self.ctx.bus, self.grid, self.wiring, self.rooms, self.spawner)
        for resource in (*resources, self.feel.player, self.feel.rooms):
            self.world.insert_resource(resource)
        self.world.insert_resource(self.grid, key=TileSource)
        self.schedule = gameplay_schedule()
        self.player = self.world.spawn(*self._new_player())
        self.world.flush()

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
            bus.subscribe(BeaconLit, self._on_beacon_lit),
            *self.progress.subscribe(bus),
        ]

    def on_exit(self) -> None:
        for unsubscribe in self._unsubscribe:
            unsubscribe()
        self.progress.save(self.spawner)

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

    def _effects(self) -> Flag:
        video = self.ctx.settings.video
        toggles = (
            (Flag.LIGHTING, True),
            (Flag.BLOOM, video.bloom),
            (Flag.GRADING, video.grading),
            (Flag.VIGNETTE, video.vignette),
            (Flag.CRT, video.crt),
            (Flag.SHADOWS, video.shadows),
            (Flag.SHAFTS, video.light_shafts),
        )
        return functools.reduce(operator.or_, (flag for flag, on in toggles if on), Flag(0))

    def _read_emitters(self) -> dict[str, EmitterSpec] | None:
        try:
            return load_emitters(paths.content(PARTICLES))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", PARTICLES, error)
            return None

    def _read_backdrops(self) -> dict[str, BackdropSpec] | None:
        try:
            return load_backdrops(paths.content(BACKDROPS))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", BACKDROPS, error)
            return None

    def _show_backdrops(self) -> None:
        self.backdrops.prepare(self._backdrop(room) for room in self.rooms.graph.levels)
        self.backdrops.show(self._backdrop(self.room), instantly=True)

    def _backdrop(self, room: str) -> str | None:
        name = self.rooms.graph.levels[room].field("Backdrop")
        if name and name not in self.backdrops.specs:
            log.warning("Room %s has unknown backdrop %r", room, name)
        return name

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

    def _continue_point(self, room: str, beacon: str) -> tuple[float, float]:
        """Feet of the `beacon` entity in `room`, or the room's start if there is none."""
        level = self.rooms.graph.levels[room]
        for entity in level.entities():
            if entity.iid == beacon:
                left = level.world_x + entity.px[0] - entity.pivot[0] * entity.width
                top = level.world_y + entity.px[1] - entity.pivot[1] * entity.height
                return left + entity.width / 2, top + entity.height
        return self._entry_point(room)

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
        emitters = self._read_emitters()
        if emitters is not None:
            self.emitters = emitters
        backdrops = self._read_backdrops()
        if backdrops is not None:
            self.backdrops = Backdrops(backdrops, self.ctx.canvas_size)
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
        self._show_backdrops()
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
        self.progress.tick(dt)
        self.particles.update(dt)
        self.flash.update(dt)
        self.backdrops.update(self._room_lit(), dt)
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
        self.progress.discover(self.rooms.graph.levels[event.room].iid)
        self.backdrops.show(self._backdrop(event.room))
        log.debug("Entered %s from %s", event.room, event.previous)

    def _room_lit(self) -> bool:
        """Whether the active room has a lit beacon."""
        return any(
            beacon.lit and identity.room == self.room
            for _, identity, beacon in self.world.query(Identity, Beacon)
        )

    def _on_beacon_lit(self, event: BeaconLit) -> None:
        juice = self.feel.juice
        self.camera.shake.add(juice.beacon_trauma)
        self.flash.start(juice.beacon_flash)
        if (burst := self.emitters.get("beacon_burst")) is not None:
            self.particles.burst(burst, event.x, event.y - 14)
        self.progress.checkpoint(event.room, event.iid, self.spawner)

    # Rendering

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        self.jobs.pump(BAKE_BUDGET)
        ox, oy = self.camera.offset(alpha)
        room_top = self.rooms.graph.rects[self.room].top
        self.backdrops.draw_far(canvas, (ox, oy), room_top)
        for layer, _ in self.layers.values():
            layer.draw(canvas, (ox, oy))
        frame = self.frame
        frame.clear()
        size = self.grid.tile_size

        def occluded(x: float, y: float) -> bool:
            column, row = math.floor((x + ox) / size), math.floor((y + oy) / size)
            return self.grid.get(column, row) == Tile.SOLID

        frame.occluded = occluded
        light = self.flicker(self.clock)
        for _, body, beacon in self.world.query(Body, Beacon):
            if beacon.lit:
                bx, by = body.center_x - ox, body.y + 3 - oy
                frame.light(bx, by, GLOW_RADIUS, GLOW, light)
                for index, spread in enumerate(SHAFT_ANGLES):
                    sway = math.sin(self.clock * 0.7 + index * 2.1) * 6
                    frame.shaft(ShaftCmd(bx, by, 270 + spread + sway, 90, 36, GLOW, light * 0.8))
        for _, body, sprite in self.world.query(Body, Sprite):
            image = self.art.image(sprite.current, (round(body.width), round(body.height)))
            frame.sprite(image, round(body.x) - ox, round(body.y) - oy)
        for _, body, interactable in self.world.query(Body, Interactable):
            if interactable.in_range:
                above = (round(body.center_x) - ox, round(body.y) - oy - 3)
                frame.sprite(*self._at(self.art.prompt, above), layer=Layer.OVERLAY)
        if self.respawn_in == 0:
            self._queue_player(light, ox, oy, alpha)
        self.backend.render(frame, canvas)
        self.particles.draw(canvas, (ox, oy))
        self.backdrops.draw_near(canvas, (ox, oy), room_top)
        self.post.apply(canvas, self.frame.flags, self.backdrops.grade())
        self.flash.draw(canvas)
        if self.show_colliders:
            self._draw_colliders(canvas, ox, oy)
        if self.show_rooms:
            self._draw_rooms(canvas, ox, oy)
            self._draw_wires(canvas, ox, oy)

    @staticmethod
    def _at(
        image: pygame.Surface, midbottom: tuple[float, float]
    ) -> tuple[pygame.Surface, int, int]:
        rect = image.get_rect(midbottom=(round(midbottom[0]), round(midbottom[1])))
        return image, rect.x, rect.y

    def _queue_player(self, light: float, ox: int, oy: int, alpha: float) -> None:
        p, body, visual = self.motor, self.body, self.visual
        px, py = p.previous
        x = px + (body.x - px) * alpha
        y = py + (body.y - py) * alpha
        feet = (x + body.width / 2 - ox, y + body.height - oy)
        lx, ly = self.sprite.lantern_offset(p.facing, visual.scale_x, visual.scale_y)
        self.frame.light(feet[0] + lx, feet[1] + ly, GLOW_RADIUS, GLOW, light)
        image = self.sprite.image(p.facing, visual.scale_x, visual.scale_y)
        self.frame.sprite(*self._at(image, feet))

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
