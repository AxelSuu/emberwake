"""Playing the world: input, player, rooms, camera, juice, placeholder rendering and dev tools."""

from __future__ import annotations

import dataclasses
import functools
import logging
import math
import operator
import time
import tomllib
from typing import TYPE_CHECKING

import pygame

from emberwake.engine.core.cutscene import CutscenePlayer
from emberwake.engine.core.dialogue import DialogueError, Graph, flags_used, load_dialogues
from emberwake.engine.core.jobs import Jobs
from emberwake.engine.core.serde import SerdeError
from emberwake.engine.debug.time_control import TimeControl
from emberwake.engine.ecs import World
from emberwake.engine.ecs.prefabs import Prefab, load_prefabs
from emberwake.engine.input import InputMapper, InputState
from emberwake.engine.input.replay import REPLAY_CODEC, Replay, ReplayPlayer, ReplayRecorder
from emberwake.engine.physics import Body, PropWorld, Tile, TileSource
from emberwake.engine.platform.documents import save_document
from emberwake.engine.render.camera import Camera
from emberwake.engine.render.chunks import ChunkLayer
from emberwake.engine.render.floating_text import FloatingTexts
from emberwake.engine.render.frame import Flag, Layer, RenderFrame, ShaftCmd
from emberwake.engine.render.hit_flash import flashed
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
from emberwake.game.combat import Damaged, Health, Hitbox, Hurtbox, Killed, Team
from emberwake.game.components import Sprite
from emberwake.game.cosmetics import Cosmetics, load_cosmetics
from emberwake.game.data.records import RunResult, format_time, load_records
from emberwake.game.data.save import SaveSlot, load_slot
from emberwake.game.dialogue import Talk
from emberwake.game.feel import Feel, diff, load_feel
from emberwake.game.flares import Flare, FlareKit
from emberwake.game.interact import Collected, Interactable, Switch
from emberwake.game.light import Ember, LightSource
from emberwake.game.player.controller import Dashed, Died, Jumped, Landed, Motor, new_player
from emberwake.game.player.swing import Swing, SwingHit, SwingStarted
from emberwake.game.player.visual import PlayerVisual
from emberwake.game.progress import Progress
from emberwake.game.render.backdrop import Backdrops, BackdropSpec, load_backdrops
from emberwake.game.render.fx import Flash
from emberwake.game.render.placeholder import EntityArt, Flicker, PlayerSprite, tile_painter
from emberwake.game.render.swing_fx import arm, lantern_point, trail
from emberwake.game.render.toast import Toasts
from emberwake.game.scenes.dev import FlagsScene, WarpScene
from emberwake.game.scenes.dialogue import DialogueScene
from emberwake.game.scenes.pause import PauseScene
from emberwake.game.scenes.results import ResultsScene, RunFinished
from emberwake.game.schedule import gameplay_schedule
from emberwake.game.shop import EMBER_PER_UPGRADE, HP_PER_UPGRADE, SPENT
from emberwake.game.signals import Receiver, Wiring
from emberwake.game.trials import (
    Ghost,
    GoalReached,
    Trial,
    load_ghost,
    load_trials,
    medal_for,
    record_key,
    save_ghost,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from emberwake.engine.core.events import EventBus
    from emberwake.game.context import GameContext

log = logging.getLogger(__name__)

WORLD = "world.ldtk"
FEEL = "feel.toml"
PREFABS = "prefabs.toml"
UP_HP = "up_hp"
UP_OIL = "up_oil"
BACKDROPS = "backdrops.toml"
PARTICLES = "particles.toml"
COSMETICS = "cosmetics.toml"
DIALOGUE = "dialogue.toml"
TRIALS = "trials.toml"
COLLISIONS = {1: Tile.SOLID, 2: Tile.ONE_WAY, 3: Tile.HAZARD}
DEFAULT_ROOM = "Test_Room"
BAKE_BUDGET = 0.002
"""Seconds per frame spent baking room art in the background."""
GLOW_RADIUS = 64
HIT_FLASH = 0.12
"""Seconds an enemy shows white after a hit."""
SHOULDER = 7
"""Px below the top of the player's body that the lantern swings around."""
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
        trial: str | None = None,
    ) -> None:
        """Continue from the save slot, or play `room`, a replay or a `trial` without saving."""
        self.ctx = ctx
        self._init_trial(trial)
        room = self.trial.room if self.trial else room
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
        self.cosmetics = self._read_cosmetics()
        self.dialogues = self._read_dialogues()
        self.sprite = PlayerSprite()
        self.glow = GLOW
        self.flicker = Flicker()
        self.frame = RenderFrame(flags=self._effects())
        self.post = PostChain(ctx.canvas_size)
        self.backend = SoftwareBackend()
        self.art = EntityArt()
        self.particles = ParticleSystem()
        self.cutscenes = CutscenePlayer()
        self.toasts = Toasts()
        self.texts = FloatingTexts()
        self.texts.muted = ctx.settings.accessibility.reduce_flashes
        self.emitters = self._read_emitters() or {}
        self.flash = Flash()
        self.flash.muted = ctx.settings.accessibility.reduce_flashes
        self.backdrops = Backdrops(self._read_backdrops() or {}, ctx.canvas_size)
        self.time = TimeControl()
        self.hitstop = 0
        self.flashes: dict[int, float] = {}
        """Seconds of white flash left per entity id."""
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
        if self.trial is not None:
            self._begin_attempt()

    def _open_progress(self, room: str | None, replay: Replay | None) -> str:
        """Load the slot unless a room or replay was asked for; return the starting room."""
        ctx = self.ctx
        from_slot = room is None and replay is None
        save = load_slot(ctx.storage, ctx.slot) if from_slot and not ctx.new_game else None
        ctx.new_game = False
        start = room or (save.room if save else DEFAULT_ROOM)
        data = save or SaveSlot(room=start)
        data.flags.update(ctx.flags)
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
        feel = self.feel
        tunings = (feel.player, feel.rooms, feel.light, feel.enemies, feel.swing)
        for resource in (*resources, *tunings):
            self.world.insert_resource(resource)
        self.world.insert_resource(self.grid, key=TileSource)
        self.world.insert_resource(FlareKit(PropWorld(self.grid, (0, 0, 1, 1))))
        self.schedule = gameplay_schedule()
        self._apply_settings()
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
            bus.subscribe(SwingStarted, self._on_swing),
            bus.subscribe(SwingHit, self._on_swing_hit),
            bus.subscribe(Died, self._on_died),
            bus.subscribe(RoomEntered, self._on_room_entered),
            bus.subscribe(RunFinished, self._on_run_finished),
            bus.subscribe(Collected, self._on_collected),
            bus.subscribe(Damaged, self._on_damaged),
            bus.subscribe(Talk, self._on_talk),
            bus.subscribe(GoalReached, self._on_goal),
            *self._track_achievements(bus),
            bus.subscribe(Killed, self._on_killed),
            bus.subscribe(BeaconLit, self._on_beacon_lit),
            *self.progress.subscribe(bus),
        ]

    def _init_trial(self, trial: str | None) -> None:
        self.trial_id = trial
        self.trial = self._read_trials()[trial] if trial else None
        self.trial_time = 0.0
        self.trial_deaths = 0
        self.trial_done = False
        self.ghost: Ghost | None = None

    def _read_trials(self) -> dict[str, Trial]:
        try:
            return load_trials(paths.content(TRIALS))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", TRIALS, error)
            return {}

    def _begin_attempt(self) -> None:
        """Start recording this attempt, and bring the saved ghost to the start line."""
        self.recorder = ReplayRecorder[Action](self.room)
        self.ghost = None
        if self.trial_id is None:
            return
        replay = load_ghost(self.ctx.storage, self.trial_id)
        if replay is not None and replay.ticks:
            self.ghost = Ghost(replay, self.spawn_point, self.feel.player)

    def _on_goal(self, _: GoalReached) -> None:
        if self.trial is None or self.trial_id is None or self.trial_done:
            return
        self.trial_done = True
        key, seconds = record_key(self.trial_id), self.trial_time
        before = load_records(self.ctx.storage).runs.get(key)
        if before is None or seconds < before.best_time:
            save_ghost(self.ctx.storage, self.trial_id, self.recorder.replay)
        medal = medal_for(self.trial, seconds)
        result = RunResult(key, seconds, deaths=self.trial_deaths, medal=medal)
        self.ctx.bus.publish(RunFinished(result))

    def _read_dialogues(self) -> dict[str, Graph]:
        try:
            return load_dialogues(paths.content(DIALOGUE))
        except (OSError, tomllib.TOMLDecodeError, SerdeError, DialogueError) as error:
            log.error("Could not load %s: %s", DIALOGUE, error)
            return {}

    def _read_cosmetics(self) -> Cosmetics:
        try:
            return load_cosmetics(paths.content(COSMETICS))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", COSMETICS, error)
            return Cosmetics()

    def _apply_settings(self) -> None:
        """Skin, lantern color and game speed from the settings."""
        settings = self.ctx.settings
        skin = self.cosmetics.skin(settings.cosmetics.skin)
        flame = self.cosmetics.lantern(settings.cosmetics.lantern, palette.EMBER_HOT)
        self.sprite = PlayerSprite({k: v for k, v in dataclasses.asdict(skin).items() if v}, flame)
        color = pygame.Color(flame)
        self.glow = (color.r, color.g, color.b)
        self.time.speed = min(max(settings.assist.game_speed, 0.25), 1.0)

    def _assist(self) -> None:
        """Keep the player topped up for the assist options that are on."""
        assist = self.ctx.settings.assist
        if not self.world.has(self.player, Ember) or self.motor.dead:
            return
        if assist.invulnerable:
            self.world.get(self.player, Health).invulnerable = 1.0
        if assist.no_ember_drain:
            ember = self.world.get(self.player, Ember)
            ember.current = ember.max
        if assist.infinite_dashes:
            self.motor.dash_charges = max(self.motor.dash_charges, self.feel.player.dash_charges)

    def _apply_upgrades(self) -> None:
        """Raise the player's maximums for upgrades bought since they were last applied."""
        if not self.world.has(self.player, Ember):
            return
        health, ember = self.world.get(self.player, Health), self.world.get(self.player, Ember)
        hp, most = self._maximums()
        if hp > health.max:
            health.current += hp - health.max
            health.max = hp
        if most > ember.max:
            ember.current += most - ember.max
            ember.max = most

    def _on_talk(self, event: Talk) -> None:
        graph = self.dialogues.get(event.dialogue)
        if graph is None:
            log.warning("No dialogue %r", event.dialogue)
            return
        self.manager.push(
            DialogueScene(self.ctx, graph, self.progress, lambda: self.progress.save(self.spawner))
        )

    def on_resume(self) -> None:
        """Apply settings changed in an overlay and drop input held while it was open."""
        if self.trial_done:
            from emberwake.game.scenes.title import TitleScene  # noqa: PLC0415

            self.manager.switch(TitleScene(self.ctx))
            return
        settings = self.ctx.settings
        self._apply_settings()
        self._apply_upgrades()
        self.mapper.bind(settings.controls)
        self.mapper.release_all()
        self.frame.flags = self._effects()
        self.camera.shake.intensity = settings.video.screen_shake
        self.flash.muted = settings.accessibility.reduce_flashes
        self.texts.muted = settings.accessibility.reduce_flashes

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

    def _new_player(self) -> tuple[object, ...]:
        body, motor = new_player(*self.spawn_point, self.feel.player)
        hp, most = self._maximums()
        health = Health(hp, iframes=self.feel.enemies.player_iframes)
        swing = Swing(), Hitbox(targets=Team.ENEMY)
        return body, motor, Ember(most, max=most), health, Hurtbox(Team.PLAYER), *swing

    def _maximums(self) -> tuple[int, float]:
        """The player's health and ember capacity, with the shop upgrades bought so far."""
        flags = self.progress.data.flags
        hp = self.feel.enemies.player_hp + flags.get(UP_HP, 0) * HP_PER_UPGRADE
        most = self.feel.light.ember_max + flags.get(UP_OIL, 0) * EMBER_PER_UPGRADE
        return hp, most

    def reload(self) -> None:
        """Re-read feel.toml, prefabs and the levels, keeping the player where it is."""
        feel = self._read_feel()
        if feel is not None:
            for key, (old, new) in sorted(diff(self.feel, feel).items()):
                log.info("feel %s: %s -> %s", key, old, new)
            self.feel = feel
            self.world.insert_resource(feel.player)
            self.world.insert_resource(feel.rooms)
            self.world.insert_resource(feel.light)
            self.world.insert_resource(feel.enemies)
            self.world.insert_resource(feel.swing)
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
                self.manager.push(PauseScene(self.ctx))
            elif event.key == pygame.K_RETURN and self.cutscenes.active:
                self.cutscenes.skip()
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
            case pygame.K_F6:
                rooms = sorted(self.rooms.graph.levels)
                self.manager.push(WarpScene(self.ctx, rooms, self.room, self.warp))
            case pygame.K_F7:
                flags = self.progress.data.flags
                self.manager.push(FlagsScene(self.ctx, flags, self._known_flags()))
            case pygame.K_F9:
                self.save_replay()
            case pygame.K_p:
                self.time.toggle_pause()
            case pygame.K_PERIOD:
                self.time.step()
            case pygame.K_COMMA:
                self.time.toggle_slow()

    def warp(self, room: str) -> None:
        """Move the player to `room`'s first PlayerStart, as if it had walked in (dev)."""
        previous = self.room
        x, y = self._entry_point(room)
        self.rooms.enter(room)
        if not self.motor.dead:
            body, motor = self.body, self.motor
            body.x, body.y = x - body.width / 2, y - body.height
            motor.vx = motor.vy = 0.0
            motor.previous = (body.x, body.y)
        self.ctx.bus.publish(RoomEntered(room, previous, x, y))
        self.spawn_point = (x, y)
        self.camera.snap(*self._camera_target())

    def _known_flags(self) -> set[str]:
        """Flags the content reads or writes, for the flag overlay."""
        names = {SPENT, UP_HP, UP_OIL}
        for graph in self.dialogues.values():
            names |= flags_used(graph)
        return names

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
        held = self.mapper.sample()
        return frozenset() if self.cutscenes.active or self.trial_done else held

    # Simulation

    def update(self, dt: float) -> None:
        if not self.time.should_tick():
            return
        self.clock += dt
        self.progress.tick(dt)
        self.cutscenes.update(dt)
        self.particles.update(dt)
        self.texts.update(dt)
        self.toasts.update(dt)
        self.flash.update(dt)
        self.flashes = {eid: left - dt for eid, left in self.flashes.items() if left > dt}
        self.backdrops.update(self._room_lit(), dt)
        juice = self.feel.juice
        self.visual.update(juice.squash_recovery, dt)
        if self.hitstop > 0:
            self.hitstop -= 1
            self.camera.shake.update(dt)
            return

        frame = self._sample()
        self.actions.advance(frame)
        if self.respawn_in > 0:
            self.respawn_in -= 1
            if self.respawn_in == 0:
                self.world.add(self.player, *self._new_player())
                if self.trial is not None:
                    self._begin_attempt()
        self.recorder.record(frame)
        self._assist()
        self.schedule.run(self.world, dt)
        if self.trial is not None and not self.trial_done:
            self.trial_time += dt
        if self.ghost is not None:
            self.ghost.update(self.grid, dt)
        if not self.free_camera:
            self.camera.update(*self._camera_target(), self.motor.facing, dt)

    def _camera_target(self) -> tuple[float, float]:
        body = self.body
        return body.center_x, body.y + body.height / 2

    # Juice

    def _on_jumped(self, event: Jumped) -> None:
        self.ctx.audio.sfx("player/jump")
        self.visual.stretch(self.feel.juice.stretch)
        if event.wall:
            self.camera.shake.add(self.feel.juice.wall_jump_trauma)

    def _on_landed(self, event: Landed) -> None:
        juice, max_fall = self.feel.juice, self.feel.player.max_fall
        impact = min(event.speed / max_fall, 1.0)
        self.ctx.audio.sfx("player/land", impact)
        self.visual.squash(juice.squash * impact)
        if impact >= juice.hard_landing:
            self.camera.shake.add(juice.hard_landing_trauma)

    def _on_dashed(self, _: Dashed) -> None:
        self.ctx.audio.sfx("player/dash")
        self.hitstop = max(self.hitstop, self.feel.juice.dash_hitstop)
        self.camera.shake.add(self.feel.juice.dash_trauma)

    def _on_swing(self, _: SwingStarted) -> None:
        self.ctx.audio.sfx("player/swing")

    def _on_swing_hit(self, event: SwingHit) -> None:
        swing = self.feel.swing
        if event.enemy:
            self.hitstop = max(self.hitstop, swing.hitstop)
            self.camera.shake.add(swing.trauma)
        self.ctx.audio.sfx("player/hit" if event.enemy else "player/clang")
        if (sparks := self.emitters.get("swing_sparks")) is not None:
            self.particles.burst(sparks, event.x, event.y)

    def _on_died(self, _: Died) -> None:
        juice = self.feel.juice
        self.hitstop = max(self.hitstop, juice.death_hitstop)
        self.camera.shake.add(juice.death_trauma)
        self.respawn_in = juice.respawn_delay
        self.trial_deaths += 1

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

    def _on_run_finished(self, event: RunFinished) -> None:
        self.manager.push(ResultsScene(self.ctx, event.result))

    def _track_achievements(self, bus: EventBus) -> list[Callable[[], None]]:
        """Feed gameplay events to the achievement counters and show toasts for unlocks."""
        tracker = self.ctx.achievements
        tracker.on_unlock = self._on_achievement

        def count(name: str) -> Callable[[object], None]:
            def handle(_: object) -> None:
                tracker.record(name)

            return handle

        def collected(event: Collected) -> None:
            tracker.record("Collected", event.value)

        def killed(event: Killed) -> None:
            if event.target != self.player:
                tracker.record("Killed")

        def entered(event: RoomEntered) -> None:
            tracker.enter_room(event.room)

        tracker.enter_room(self.room)
        return [
            bus.subscribe(Jumped, count("Jumped")),
            bus.subscribe(Dashed, count("Dashed")),
            bus.subscribe(Died, count("Died")),
            bus.subscribe(BeaconLit, count("BeaconLit")),
            bus.subscribe(Collected, collected),
            bus.subscribe(Killed, killed),
            bus.subscribe(RoomEntered, entered),
        ]

    def _on_achievement(self, ident: str) -> None:
        name = self.ctx.t(f"achievement.{ident}.name")
        self.toasts.push(self.ctx.t("achievement.unlocked", name=name))

    def _on_damaged(self, event: Damaged) -> None:
        hurt_player = event.target == self.player
        if hurt_player:
            self.hitstop = max(self.hitstop, self.feel.juice.dash_hitstop + 1)
            self.camera.shake.add(self.feel.juice.dash_trauma)
        if not hurt_player and not self.flash.muted:
            self.flashes[event.target] = HIT_FLASH
        color = pygame.Color(palette.EMBER_COOL if hurt_player else palette.MIST)
        self.texts.spawn(f"-{event.amount}", event.x, event.y - 8, (color.r, color.g, color.b))

    def _on_killed(self, event: Killed) -> None:
        if event.target == self.player and not self.motor.dead:
            self.motor.dead = True
            body = self.body
            self.ctx.bus.publish(Died(body.center_x, body.bottom))

    def _on_collected(self, event: Collected) -> None:
        body, color = self.body, pygame.Color(palette.EMBER_HOT)
        self.texts.spawn(f"+{event.value}", body.center_x, body.y - 4, (color.r, color.g, color.b))

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
        self._queue_world(light, ox, oy)
        if self.respawn_in == 0:
            self._queue_player(light, ox, oy, alpha)
        self.backend.render(frame, canvas)
        self.particles.draw(canvas, (ox, oy))
        self.texts.draw(canvas, (ox, oy))
        self.backdrops.draw_near(canvas, (ox, oy), room_top)
        self.post.apply(canvas, self.frame.flags, self.backdrops.grade())
        self.flash.draw(canvas)
        self._draw_ember(canvas)
        self._draw_trial_timer(canvas)
        self.toasts.draw(canvas)
        if self.show_colliders:
            self._draw_colliders(canvas, ox, oy)
        if self.show_rooms:
            self._draw_rooms(canvas, ox, oy)
            self._draw_wires(canvas, ox, oy)

    def _queue_world(self, light: float, ox: int, oy: int) -> None:
        """Lights, shafts and entity sprites into the frame."""
        frame = self.frame
        for _, body, beacon in self.world.query(Body, Beacon):
            if beacon.lit:
                bx, by = body.center_x - ox, body.y + 3 - oy
                frame.light(bx, by, GLOW_RADIUS, GLOW, light)
                for index, spread in enumerate(SHAFT_ANGLES):
                    sway = math.sin(self.clock * 0.7 + index * 2.1) * 6
                    frame.shaft(ShaftCmd(bx, by, 270 + spread + sway, 90, 36, GLOW, light * 0.8))
        for eid, body, source in self.world.query(Body, LightSource):
            fx, fy = body.center_x - ox, body.y + body.height / 2 - oy
            frame.light(fx, fy, round(source.radius), GLOW, light * source.strength)
            if self.world.has(eid, Flare):
                image = self.art.image("flare", (round(body.width), round(body.height)))
                frame.sprite(image, round(body.x) - ox, round(body.y) - oy)
        for eid, body, sprite in self.world.query(Body, Sprite):
            image = self.art.image(sprite.current, (round(body.width), round(body.height)))
            if eid in self.flashes:
                image = flashed(image, self.flashes[eid] / HIT_FLASH)
            frame.sprite(image, round(body.x) - ox, round(body.y) - oy)
        for _, body, interactable in self.world.query(Body, Interactable):
            if interactable.in_range:
                above = (round(body.center_x) - ox, round(body.y) - oy - 3)
                frame.sprite(*self._at(self.art.prompt, above), layer=Layer.OVERLAY)

    def _draw_trial_timer(self, canvas: pygame.Surface) -> None:
        if self.trial is None:
            return
        font = self._hud_font = getattr(self, "_hud_font", None) or pygame.font.Font(None, 16)
        text = font.render(format_time(self.trial_time), False, palette.MIST)
        canvas.blit(text, text.get_rect(midtop=(canvas.get_width() // 2, 6)))

    def _draw_ember(self, canvas: pygame.Surface) -> None:
        """A small bar of the player's ember in the top left corner."""
        if not self.world.has(self.player, Ember):
            return
        ember = self.world.get(self.player, Ember)
        fraction = ember.current / ember.max
        x, y, width = 6, 6, 40
        canvas.fill(palette.INK, (x - 1, y - 1, width + 2, 5))
        color = palette.EMBER_HOT if fraction > 0.25 else palette.EMBER_COOL
        canvas.fill(color, (x, y, round(width * fraction), 3))

    @staticmethod
    def _centred(
        image: pygame.Surface, centre: tuple[float, float]
    ) -> tuple[pygame.Surface, int, int]:
        rect = image.get_rect(center=(round(centre[0]), round(centre[1])))
        return image, rect.x, rect.y

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
        lantern = (feet[0] + lx, feet[1] + ly)
        swing = self.world.find(self.player, Swing)
        swinging = swing is not None and swing.tick > 0
        if swing is not None and swinging:
            shoulder = (feet[0], y + SHOULDER - oy)
            lantern = lantern_point(swing, self.feel.swing, shoulder, lantern)
            if (arc := trail(swing, self.feel.swing)) is not None:
                self.frame.sprite(*self._centred(arc, shoulder), layer=Layer.FOREGROUND)
        self.frame.light(*lantern, GLOW_RADIUS, self.glow, light)
        image = self.sprite.image(p.facing, visual.scale_x, visual.scale_y, bare=swinging)
        self.frame.sprite(*self._at(image, feet))
        if swing is not None and swinging:
            shoulder = (round(feet[0]), round(y + SHOULDER - oy))
            image, (left, top) = arm(lantern[0] - shoulder[0], lantern[1] - shoulder[1])
            self.frame.sprite(image, shoulder[0] + left, shoulder[1] + top)
            self.frame.sprite(*self._centred(self.sprite.lantern, lantern))
        self._queue_ghost(ox, oy)

    def _queue_ghost(self, ox: int, oy: int) -> None:
        ghost = self.ghost
        if ghost is None or ghost.finished:
            return
        body, motor = ghost.body, ghost.motor
        image = self.sprite.image(motor.facing, 1.0, 1.0).copy()
        image.set_alpha(110)
        feet = (body.x + body.width / 2 - ox, body.y + body.height - oy)
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
