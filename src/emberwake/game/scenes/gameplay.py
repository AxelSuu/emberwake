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
from emberwake.engine.ecs import EntityId, World
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
from emberwake.game.areas import (
    AreaGrade,
    AreaLight,
    Areas,
    LightCensus,
    area_of,
    describe,
    load_areas,
    music_of,
)
from emberwake.game.beacons import Beacon, BeaconLit, Rested
from emberwake.game.breakables import Broken, Crumble, Crumbled
from emberwake.game.cinder import CinderRecovered, cinder_parts
from emberwake.game.combat import Damaged, Health, Hitbox, Hurtbox, Killed, Team
from emberwake.game.components import Sprite
from emberwake.game.cosmetics import Cosmetics, load_cosmetics
from emberwake.game.data.records import RunResult, format_time, load_records, save_records, unlock
from emberwake.game.data.save import Cinder, SaveSlot, load_slot
from emberwake.game.dialogue import Talk
from emberwake.game.encounters import EncounterCleared, EncounterStarted
from emberwake.game.enemies import KINDS, Brain, Summoned, Toppled, Vented
from emberwake.game.feel import Feel, diff, load_feel
from emberwake.game.flags import Facts, admits, flags_in
from emberwake.game.flares import Flare, FlareFizzled, FlareKit, FlareThrown
from emberwake.game.grants import Give, Granted, GrantSpec, Loadout, load_grants
from emberwake.game.interact import Collected, Interactable, Switch
from emberwake.game.lamprey import (
    Bitten,
    Breached,
    CasingBroken,
    Drained,
    Lamprey,
    LampreyDefeated,
    PhaseChanged,
)
from emberwake.game.lamps import LampLit, LampSnuffed
from emberwake.game.light import Ember, LightSource
from emberwake.game.lore import EchoHeard, EchoPlay, speeches
from emberwake.game.lost_lights import LostLightRescued, Spirit
from emberwake.game.player.controller import Dashed, Died, Jumped, Landed, Motor, new_player
from emberwake.game.player.kindle import Kindle, Kindled
from emberwake.game.player.swing import Swing, SwingHit, SwingStarted
from emberwake.game.player.visual import PlayerVisual
from emberwake.game.progress import Progress
from emberwake.game.render.backdrop import Backdrops, BackdropSpec, load_backdrops
from emberwake.game.render.bank import SpriteBank
from emberwake.game.render.bubble import Bubbles
from emberwake.game.render.fx import Flash
from emberwake.game.render.glow import Glows
from emberwake.game.render.hud import Hud, HudState
from emberwake.game.render.lamprey_view import LampreyView
from emberwake.game.render.placeholder import EntityArt, Flicker, PlayerSprite, tile_painter
from emberwake.game.render.player_view import Light, PlayerView
from emberwake.game.render.toast import Toasts
from emberwake.game.scenes.dev import FlagsScene, WarpScene
from emberwake.game.scenes.dialogue import DialogueScene
from emberwake.game.scenes.pause import PauseScene
from emberwake.game.scenes.results import ResultsScene, RunFinished
from emberwake.game.schedule import gameplay_schedule
from emberwake.game.shop import EMBER_PER_UPGRADE, HP_PER_UPGRADE, SPENT, wallet
from emberwake.game.signals import Receiver, Wiring
from emberwake.game.switches import BellRung, BrazierLit
from emberwake.game.trials import (
    Ghost,
    GoalReached,
    Trial,
    TrialDoorUsed,
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
GRANTS = "grants.toml"
AREAS = "areas.toml"
COLLISIONS = {1: Tile.SOLID, 2: Tile.ONE_WAY, 3: Tile.HAZARD}
DEFAULT_ROOM = "Wake"
BAKE_BUDGET = 0.002
"""Seconds per frame spent baking room art in the background."""
GLOW_RADIUS = 72
FLICKER_PHASE = 1.37
"""Seconds of flicker between entities with consecutive ids, so lights do not pulse together."""
BRIGHTNESS_LIFT = 0.6
"""How far the brightness setting at full lifts the darkness toward full light."""
WALKING = frozenset({"patrol", "charge", "creep", "flee"})
"""Brain states in which a placeholder enemy bobs as it walks."""
TREMBLING = frozenset({"warn", "hiss", "rear", "call"})
"""Brain states in which a placeholder enemy shakes before it acts."""
LANDING_DUST = 0.35
"""Share of the fall speed above which a landing kicks up dust."""
TREMBLE_RATE = 30.0
"""Sideways flips per second of a crumbling platform about to go."""
HIT_FLASH = 0.12
"""Seconds an enemy shows white after a hit."""
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
        self._init_render()
        self.particles = ParticleSystem()
        self.cutscenes = CutscenePlayer()
        self.toasts = Toasts()
        self.bubbles = Bubbles()
        self.hud = Hud()
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
        self._init_respawn()
        self.clock = 0.0
        self.show_colliders = False
        self.show_rooms = False
        self.free_camera = False
        self._unsubscribe: list[Callable[[], None]] = []
        self.jobs = Jobs()
        self.layers: dict[str, tuple[ChunkLayer, Iterator[None]]] = {}
        self._build_world(start)
        self._show_backdrops()
        self._init_areas()
        self.camera.snap(*self._camera_target())
        if self.trial is not None:
            self._begin_attempt()

    def _init_respawn(self) -> None:
        self.respawn_in = 0
        self.to_beacon = False
        """The coming respawn is at the last beacon (a death), not the room's entrance."""
        self.kept: tuple[int, float] | None = None
        """Health and flame to keep through a respawn after a hazard."""
        self.safe = (0.0, 0.0)
        """The last place the player stood on solid ground, for dropping the Cinder."""
        self.cinder: EntityId | None = None
        """The live Cinder entity, if its room is loaded."""

    def _init_render(self) -> None:
        self.sprite = PlayerSprite()
        self.glow = GLOW
        self.flicker = Flicker()
        self.frame = RenderFrame(flags=self._effects())
        self.post = PostChain(self.ctx.canvas_size)
        self.backend = SoftwareBackend()
        self.art = EntityArt()
        self.bank = SpriteBank(paths.sprites())
        self.glows = Glows()
        self.lampreys: dict[EntityId, LampreyView] = {}
        self.view = PlayerView(self.sprite, self.bank, self.glows)
        self._colors: dict[str, tuple[int, int, int]] = {}

    def _open_progress(self, room: str | None, replay: Replay | None) -> str:
        """Load the slot unless a room or replay was asked for; return the starting room."""
        ctx = self.ctx
        from_slot = room is None and replay is None
        save = load_slot(ctx.storage, ctx.slot) if from_slot and not ctx.new_game else None
        ctx.new_game = False
        start = room or (replay.start if replay else "") or (save.room if save else DEFAULT_ROOM)
        data = save or SaveSlot(room=start)
        data.flags.update(ctx.flags)
        self.progress = Progress(data, ctx.storage, ctx.slot if from_slot else None)
        return start

    def _build_world(self, start: str) -> None:
        self.world = World()
        data = self.progress.data
        self.facts = Facts(data.flags, data.abilities, data.inventory)
        gate = functools.partial(admits, facts=self.facts)
        self.spawner = Spawner(self.world, self._read_prefabs() or {}, data.world, gate=gate)
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
        self.world.insert_resource(self.facts)
        feel = self.feel
        tunings = (
            feel.player,
            feel.rooms,
            feel.light,
            feel.lamps,
            feel.enemies,
            feel.swing,
            feel.switches,
            feel.breakables,
            feel.encounters,
            feel.lamprey,
        )
        for resource in (*resources, *tunings):
            self.world.insert_resource(resource)
        self.world.insert_resource(self.grid, key=TileSource)
        flares = self.feel.light.flare_charges
        kit = FlareKit(PropWorld(self.grid, (0, 0, 1, 1)), charges=flares, max_charges=flares)
        self.world.insert_resource(kit)
        self.loadout = Loadout(data.abilities, data.inventory, self._read_grants())
        self.world.insert_resource(self.loadout)
        kit.max_charges = kit.charges = self._flare_charges()
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
            bus.subscribe(Broken, self._on_broken),
            bus.subscribe(Crumbled, self._on_crumbled),
            bus.subscribe(Died, self._on_died),
            bus.subscribe(RoomEntered, self._on_room_entered),
            bus.subscribe(RunFinished, self._on_run_finished),
            bus.subscribe(Collected, self._on_collected),
            bus.subscribe(Damaged, self._on_damaged),
            bus.subscribe(Vented, self._on_vented),
            bus.subscribe(Summoned, self._on_summoned),
            bus.subscribe(Toppled, self._on_toppled),
            bus.subscribe(EncounterStarted, self._on_encounter),
            bus.subscribe(EncounterCleared, self._on_encounter),
            *self._subscribe_lamprey(bus),
            bus.subscribe(Talk, self._on_talk),
            bus.subscribe(GoalReached, self._on_goal),
            bus.subscribe(TrialDoorUsed, self._on_trial_door),
            *self._track_achievements(bus),
            bus.subscribe(Killed, self._on_killed),
            bus.subscribe(BeaconLit, self._on_beacon_lit),
            bus.subscribe(Rested, self._on_rested),
            bus.subscribe(Kindled, self._on_kindled),
            bus.subscribe(CinderRecovered, self._on_cinder),
            bus.subscribe(Give, self._on_give),
            bus.subscribe(EchoHeard, self._on_echo),
            bus.subscribe(LostLightRescued, self._on_rescued),
            bus.subscribe(Granted, self._on_granted),
            bus.subscribe(FlareThrown, self._on_flare),
            bus.subscribe(FlareFizzled, self._on_fizzle),
            bus.subscribe(BrazierLit, self._on_brazier_lit),
            bus.subscribe(BellRung, self._on_bell),
            bus.subscribe(BeaconLit, self._on_light_changed),
            bus.subscribe(LampLit, self._on_lamp_lit),
            bus.subscribe(LampSnuffed, self._on_lamp_snuffed),
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

    def _on_trial_door(self, event: TrialDoorUsed) -> None:
        """Unlock the door's trial in the menu and start it."""
        if self.trial is not None:
            return
        if event.trial not in self._read_trials():
            log.warning("Trial door to unknown trial %r", event.trial)
            return
        records = load_records(self.ctx.storage)
        unlock(records, event.trial)
        save_records(self.ctx.storage, records)
        self.manager.switch(GameplayScene(self.ctx, trial=event.trial))

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
        self.view.sprite = self.sprite
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
        kit = self.world.resource(FlareKit)
        if (charges := self._flare_charges()) > kit.max_charges:
            kit.charges += charges - kit.max_charges
            kit.max_charges = charges

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
        # Baked over later frames, by when doors, walls and platforms have changed their cells.
        level_tiles = dataclasses.replace(room.grid, cells=bytearray(room.grid.cells))
        layer = ChunkLayer(room.rect.topleft, room.rect.size, tile_painter(level_tiles))
        job = layer.bake()
        self.layers[room.name] = (layer, job)
        self.jobs.add(job)
        self.spawner.spawn_room(room)
        self._place_cinder()

    def _room_unloaded(self, room: Room) -> None:
        self.spawner.despawn_room(room)
        cinder = self.progress.data.cinder
        if cinder is not None and cinder.room == room.name:
            self.cinder = None
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
        hurtbox = Hurtbox(Team.PLAYER)
        return body, motor, Ember(most, max=most), health, hurtbox, *swing, Kindle()

    def _maximums(self) -> tuple[int, float]:
        """The player's health and flame capacity, with shop upgrades and items found."""
        flags, loadout = self.progress.data.flags, self.loadout
        hp = self.feel.enemies.player_hp + flags.get(UP_HP, 0) * HP_PER_UPGRADE
        hp += loadout.bonus_health
        most = self.feel.light.ember_max + flags.get(UP_OIL, 0) * EMBER_PER_UPGRADE
        most += loadout.bonus_flame
        return hp, most

    def _flare_charges(self) -> int:
        return self.feel.light.flare_charges + self.loadout.bonus_flares

    def _read_grants(self) -> dict[str, GrantSpec]:
        try:
            return load_grants(paths.content(GRANTS))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", GRANTS, error)
            return {}

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
            self.world.insert_resource(feel.lamps)
            self.world.insert_resource(feel.enemies)
            self.world.insert_resource(feel.swing)
            self.world.insert_resource(feel.breakables)
            self.world.insert_resource(feel.switches)
            self.world.insert_resource(feel.encounters)
            self.world.insert_resource(feel.lamprey)
            self.camera.retune(feel.camera)
        prefabs = self._read_prefabs()
        if prefabs is not None:
            self.spawner.prefabs = prefabs
        emitters = self._read_emitters()
        if emitters is not None:
            self.emitters = emitters
        self.bank.reload()
        self.glows.clear()
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
        self._read_area_config()
        self._count_light()
        log.info("Reloaded")

    # Input

    def handle(self, event: pygame.Event) -> None:
        self.mapper.handle(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._count_light()
                self.manager.push(PauseScene(self.ctx, *self._area_text()))
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
                self._flags_overlay()
            case pygame.K_F9:
                self.save_replay()
            case pygame.K_p:
                self.time.toggle_pause()
            case pygame.K_PERIOD:
                self.time.step()
            case pygame.K_COMMA:
                self.time.toggle_slow()

    def _flags_overlay(self) -> None:
        data, specs = self.progress.data, self.loadout.specs
        abilities = [name for name, spec in specs.items() if spec.kind == "ability"]
        flags = self._known_flags()
        self.manager.push(FlagsScene(self.ctx, data.flags, flags, data.abilities, abilities))

    def warp(self, room: str) -> None:
        """Move the player to `room`'s first PlayerStart, as if it had walked in (dev)."""
        x, y = self._entry_point(room)
        self._enter_room(room, (x, y))
        if not self.motor.dead:
            body, motor = self.body, self.motor
            body.x, body.y = x - body.width / 2, y - body.height
            motor.vx = motor.vy = 0.0
            motor.previous = (body.x, body.y)
            self.view.place(body, motor)
        self.camera.snap(*self._camera_target())

    def _enter_room(self, room: str, feet: tuple[float, float]) -> None:
        """Make `room` the active one, streaming around it; the player will stand at `feet`."""
        previous = self.room
        self.rooms.enter(room)
        self.ctx.bus.publish(RoomEntered(room, previous, *feet))
        self.spawn_point = feet

    def _known_flags(self) -> set[str]:
        """Flags the content reads or writes, for the flag overlay."""
        names = {SPENT, UP_HP, UP_OIL}
        for graph in self.dialogues.values():
            names |= flags_used(graph)
        return names | flags_in(self.rooms.graph.levels.values())

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
        self.hud.update(dt)
        self.flash.update(dt)
        self.flashes = {eid: left - dt for eid, left in self.flashes.items() if left > dt}
        self.backdrops.update(self._room_lit(), dt)
        self.area_grade.update(dt)
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
                self._respawn()
        self.recorder.record(frame)
        self._assist()
        self.schedule.run(self.world, dt)
        if self.trial is not None and not self.trial_done:
            self.trial_time += dt
        if self.ghost is not None:
            self.ghost.update(self.grid, dt)
        self._animate_lampreys(dt)
        if not self.motor.dead:
            self._animate(dt)
        if self.motor.grounded and not self.motor.dead:
            self.safe = (self.body.center_x, self.body.bottom)
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
        if impact > LANDING_DUST:
            self._dust("land_dust", event.x, event.y)
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

    def _on_broken(self, event: Broken) -> None:
        tuning = self.feel.breakables
        self.hitstop = max(self.hitstop, tuning.hitstop)
        self.camera.shake.add(tuning.trauma)
        self.ctx.audio.sfx("world/break")
        self._dust("debris", event.x + event.width / 2, event.y + event.height / 2)

    def _on_crumbled(self, event: Crumbled) -> None:
        self.ctx.audio.sfx("world/crumble")
        self._dust("crumble_dust", event.x + event.width / 2, event.y + event.height / 2)

    def _on_died(self, event: Died) -> None:
        juice = self.feel.juice
        self.hitstop = max(self.hitstop, juice.death_hitstop)
        self.camera.shake.add(juice.death_trauma)
        self.respawn_in = juice.respawn_delay
        self.trial_deaths += 1
        self.to_beacon, self.kept = False, None
        if self.trial is not None:
            return
        health, ember = self.world.find(self.player, Health), self.world.find(self.player, Ember)
        if event.cause == "hazard" and health is not None and health.current > 1:
            self.kept = (health.current - 1, ember.current if ember is not None else 0.0)
            color = pygame.Color(palette.EMBER_COOL)
            self.texts.spawn("-1", event.x, event.y - 20, (color.r, color.g, color.b))
            return
        self.to_beacon = True
        self._drop_cinder()

    def _animate(self, dt: float) -> None:
        """Secondary motion and the dust and footsteps it calls for."""
        body, motor = self.body, self.motor
        for event in self.visual.animate(motor, dt):
            if event == "step":
                self.ctx.audio.sfx("player/step", 0.5)
                self._dust("step_dust", body.center_x, body.bottom)
            else:
                side = 1 if motor.facing > 0 else -1
                self._dust("slide_dust", body.center_x + side * body.width / 2, body.y + 6)
        swing, kindle = self.world.find(self.player, Swing), self.world.find(self.player, Kindle)
        self.view.update(body, motor, swing, kindle, dt)

    def _animate_lampreys(self, dt: float) -> None:
        """Advance the body chain of every Lamprey, and forget the views of those gone."""
        live = {eid: (body, lamprey) for eid, body, lamprey in self.world.query(Body, Lamprey)}
        self.lampreys = {eid: view for eid, view in self.lampreys.items() if eid in live}
        for eid, (body, lamprey) in live.items():
            self.lampreys.setdefault(eid, LampreyView()).update(body, lamprey, dt)

    def _dust(self, emitter: str, x: float, y: float) -> None:
        if (spec := self.emitters.get(emitter)) is not None:
            self.particles.burst(spec, x, y)

    def _respawn(self) -> None:
        """Bring the player back: at the room's entrance after a hazard, else at the beacon."""
        if self.to_beacon:
            data = self.progress.data
            room = data.room if data.room in self.rooms.graph.levels else self.room
            self._enter_room(room, self._continue_point(room, data.beacon))
            self.world.resource(FlareKit).fill()
            for loaded in self.rooms.loaded.values():
                self.spawner.spawn_room(loaded)
        self.world.add(self.player, *self._new_player())
        self.world.flush()
        if self.kept is not None:
            self.world.get(self.player, Health).current = self.kept[0]
            self.world.get(self.player, Ember).current = self.kept[1]
        self.view.place(self.body, self.motor)
        if self.to_beacon:
            self.camera.snap(*self._camera_target())
        if self.trial is not None:
            self._begin_attempt()

    def _drop_cinder(self) -> None:
        """Leave the embers carried where the player last stood; an older Cinder is lost."""
        data = self.progress.data
        if data.cinder is not None:
            data.flags[SPENT] = data.flags.get(SPENT, 0) + data.cinder.embers
            data.cinder = None
            if self.cinder is not None:
                self.world.despawn(self.cinder)
                self.cinder = None
        carried = wallet(data)
        if carried > 0:
            data.cinder = Cinder(self.room, *self.safe, carried)
            self._place_cinder()
        self.progress.save(self.spawner)

    def _place_cinder(self) -> None:
        cinder = self.progress.data.cinder
        if cinder is None or self.cinder is not None or cinder.room not in self.rooms.loaded:
            return
        self.cinder = self.world.spawn(*cinder_parts(cinder))

    def _on_give(self, event: Give) -> None:
        if self.loadout.give(event.thing, event.count):
            self.ctx.bus.publish(Granted(event.thing, event.count))

    def _on_granted(self, event: Granted) -> None:
        name = self.ctx.t(f"grant.{event.thing}.name")
        self.toasts.push(self.ctx.t("grant.found", name=name))
        self.ctx.audio.sfx("player/kindle")
        self._apply_upgrades()
        body = self.body
        self._dust("kindle", body.center_x, body.y)
        self.progress.save(self.spawner)

    def _on_echo(self, event: EchoHeard) -> None:
        if not event.first:
            return
        self.toasts.push(self.ctx.t("lore.echo_heard"))
        self.ctx.audio.sfx("player/kindle")
        self.progress.save(self.spawner)

    def _on_rescued(self, event: LostLightRescued) -> None:
        self.toasts.push(self.ctx.t("lore.rescued"))
        self.ctx.audio.sfx("player/kindle")
        if (burst := self.emitters.get("kindle")) is not None:
            self.particles.burst(burst, event.x, event.y)
        self.progress.save(self.spawner)

    def _on_cinder(self, event: CinderRecovered) -> None:
        self.progress.data.cinder = None
        self.cinder = None
        self.ctx.audio.sfx("player/kindle")
        if (burst := self.emitters.get("kindle")) is not None:
            self.particles.burst(burst, event.x, event.y)
        color = pygame.Color(palette.EMBER_HOT)
        self.texts.spawn(f"+{event.embers}", event.x, event.y - 10, (color.r, color.g, color.b))

    # Rooms

    def _on_room_entered(self, event: RoomEntered) -> None:
        self.camera.glide_to(self.rooms.graph.rects[event.room])
        self.spawn_point = self._entry_point(event.room, (event.x, event.y))
        self.progress.discover(self.rooms.graph.levels[event.room].iid)
        self.backdrops.show(self._backdrop(event.room))
        self._enter_area(event.room)
        log.debug("Entered %s from %s", event.room, event.previous)

    def _room_lit(self) -> bool:
        """Whether the active room has a lit beacon."""
        return any(
            beacon.lit and identity.room == self.room
            for _, identity, beacon in self.world.query(Identity, Beacon)
        )

    # Areas

    def _init_areas(self) -> None:
        self.area_grade = AreaGrade()
        self.area = ""
        self.light: dict[str, AreaLight] = {}
        self._read_area_config()
        self._enter_area(self.room, instantly=True)

    def _read_area_config(self) -> None:
        try:
            self.areas = load_areas(paths.content(AREAS))
        except (OSError, tomllib.TOMLDecodeError, SerdeError) as error:
            log.error("Could not load %s: %s", AREAS, error)
            self.areas = Areas()
        levels, prefabs = self.rooms.graph.levels.values(), self.spawner.prefabs
        self.census = LightCensus(levels, prefabs, self.areas.light)
        self.area_grade.dim, self.area_grade.rate = self.areas.dim, self.areas.rate

    def _enter_area(self, room: str, *, instantly: bool = False) -> None:
        area = area_of(self.rooms.graph.levels[room])
        if area == self.area:
            return
        self.area = area
        self._count_light(instantly=instantly)
        if self.trial is None:
            self.hud.banner(*self._area_text())

    def _area_text(self) -> tuple[str, str]:
        return describe(self.area, self.light.get(self.area, AreaLight()), self.ctx.t)

    def _count_light(self, *, instantly: bool = False) -> None:
        """Recount every area's light, and aim the grade at the active area's."""
        self.spawner.snapshot_all()
        self.light = self.census.count(self.spawner.state)
        self.area_grade.aim(self.light.get(self.area, AreaLight()).fraction, instantly=instantly)

    def _on_light_changed(self, _: object) -> None:
        self._count_light()

    @property
    def music(self) -> str:
        """The stem set the active room plays (no music system plays it yet)."""
        return music_of(self.rooms.graph.levels[self.room], self.areas)

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

    def _on_vented(self, event: Vented) -> None:
        if (puff := self.emitters.get("steam")) is not None:
            self.particles.burst(puff, event.x, event.y - 6)

    def _on_summoned(self, event: Summoned) -> None:
        if (puff := self.emitters.get("land_dust")) is not None:
            self.particles.burst(puff, event.x, event.y)

    def _on_toppled(self, event: Toppled) -> None:
        self.camera.shake.add(self.feel.juice.dash_trauma)
        if (puff := self.emitters.get("land_dust")) is not None:
            self.particles.burst(puff, event.x, event.y + 12)

    def _on_encounter(self, _: EncounterStarted | EncounterCleared) -> None:
        self.camera.shake.add(self.feel.encounters.trauma)

    def _subscribe_lamprey(self, bus: EventBus) -> list[Callable[[], None]]:
        def shake(event: object) -> None:
            self.camera.shake.add(self.feel.juice.dash_trauma)

        def burst(emitter: str) -> Callable[[Bitten | Breached | CasingBroken], None]:
            return lambda event: self._dust(emitter, event.x, event.y)

        return [
            bus.subscribe(Bitten, shake),
            bus.subscribe(Bitten, burst("debris")),
            bus.subscribe(Breached, burst("land_dust")),
            bus.subscribe(CasingBroken, burst("debris")),
            bus.subscribe(CasingBroken, shake),
            bus.subscribe(Drained, shake),
            bus.subscribe(PhaseChanged, shake),
            bus.subscribe(LampreyDefeated, self._on_lamprey_defeated),
        ]

    def _on_lamprey_defeated(self, event: LampreyDefeated) -> None:
        juice = self.feel.juice
        self.hitstop = max(self.hitstop, juice.death_hitstop)
        self.camera.shake.add(juice.death_trauma)
        self.flash.start(juice.beacon_flash)
        self._dust("debris", event.x, event.y)
        self.ctx.audio.sfx("world/break")
        self.progress.save(self.spawner)

    def _on_killed(self, event: Killed) -> None:
        if event.target == self.player and not self.motor.dead:
            self.motor.dead = True
            body = self.body
            self.ctx.bus.publish(Died(body.center_x, body.bottom, cause="health"))

    def _on_collected(self, event: Collected) -> None:
        body, color = self.body, pygame.Color(palette.EMBER_HOT)
        self.texts.spawn(f"+{event.value}", body.center_x, body.y - 4, (color.r, color.g, color.b))

    def _on_flare(self, _: FlareThrown) -> None:
        self.ctx.audio.sfx("player/throw")

    def _on_fizzle(self, _: FlareFizzled) -> None:
        self.ctx.audio.sfx("player/fizzle")

    def _on_brazier_lit(self, event: BrazierLit) -> None:
        self.ctx.audio.sfx("world/ignite")
        if (burst := self.emitters.get("beacon_burst")) is not None:
            self.particles.burst(burst, event.x, event.y - 6)

    def _on_bell(self, _: BellRung) -> None:
        self.ctx.audio.sfx("world/bell")
        self.camera.shake.add(self.feel.switches.bell_trauma)

    def _on_rested(self, _: Rested) -> None:
        self.world.resource(FlareKit).fill()
        if (ember := self.world.find(self.player, Ember)) is not None:
            ember.current = ember.max

    def _on_kindled(self, event: Kindled) -> None:
        self.ctx.audio.sfx("player/kindle")
        self.visual.squash(self.feel.juice.squash * 0.5)
        if (burst := self.emitters.get("kindle")) is not None:
            self.particles.burst(burst, event.x, event.y)
        color = pygame.Color(palette.EMBER_CORE)
        self.texts.spawn("+1", event.x, event.y - 14, (color.r, color.g, color.b))

    def _on_beacon_lit(self, event: BeaconLit) -> None:
        juice = self.feel.juice
        self.camera.shake.add(juice.beacon_trauma)
        self.flash.start(juice.beacon_flash)
        if (burst := self.emitters.get("beacon_burst")) is not None:
            self.particles.burst(burst, event.x, event.y - 14)
        self.progress.checkpoint(event.room, event.iid, self.spawner)

    def _on_lamp_lit(self, event: LampLit) -> None:
        self.ctx.audio.sfx("player/kindle")
        if (burst := self.emitters.get("kindle")) is not None:
            self.particles.burst(burst, event.x, event.y - 8)
        self._lamps_changed()

    def _on_lamp_snuffed(self, _: LampSnuffed) -> None:
        self.ctx.audio.sfx("player/fizzle")
        self._lamps_changed()

    def _lamps_changed(self) -> None:
        self._count_light()
        if self.trial is None:
            self.hud.banner(*self._area_text())

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
        frame.ambient = self._ambient()
        frame.occluder_version = self.grid.version
        self._queue_world(ox, oy)
        if self.respawn_in == 0:
            self._queue_player(self._flicker(self.player), ox, oy, alpha)
        self.backend.render(frame, canvas)
        self.particles.draw(canvas, (ox, oy))
        self.texts.draw(canvas, (ox, oy))
        self.backdrops.draw_near(canvas, (ox, oy), room_top)
        self.post.apply(canvas, self.frame.flags, self.area_grade.apply(self.backdrops.grade()))
        self.flash.draw(canvas)
        self._draw_speech(canvas, ox, oy)
        self._draw_hud(canvas)
        self._draw_trial_timer(canvas)
        self.toasts.draw(canvas)
        if self.show_colliders:
            self._draw_colliders(canvas, ox, oy)
        if self.show_rooms:
            self._draw_rooms(canvas, ox, oy)
            self._draw_wires(canvas, ox, oy)

    def _queue_world(self, ox: int, oy: int) -> None:
        """Lights, shafts and entity sprites into the frame; each light flickers on its own."""
        frame = self.frame
        for eid, body, beacon in self.world.query(Body, Beacon):
            if beacon.lit:
                light = self._flicker(eid)
                bx, by = body.center_x - ox, body.y + 3 - oy
                radius = round(self.feel.light.beacon_radius)
                frame.light(bx, by, radius, GLOW, light, key=self._still(eid, body))
                for index, spread in enumerate(SHAFT_ANGLES):
                    sway = math.sin(self.clock * 0.7 + index * 2.1) * 6
                    frame.shaft(ShaftCmd(bx, by, 270 + spread + sway, 90, 36, GLOW, light * 0.8))
        for eid, body, source in self.world.query(Body, LightSource):
            fx, fy = body.center_x - ox, body.y + body.height / 2 - oy
            color = self._light_color(source.color)
            strength = self._flicker(eid) * source.strength
            moving = self.world.has(eid, Flare) or self.world.has(eid, Spirit)
            key = None if moving else self._still(eid, body)
            frame.light(fx, fy, round(source.radius), color, strength, key=key)
            if self.world.has(eid, Flare):
                image = self.art.image("flare", (round(body.width), round(body.height)))
                self._queue_lit(image, round(body.x) - ox, round(body.y) - oy)
        self._queue_lampreys(ox, oy)
        for _, play in self.world.query(EchoPlay):
            if play.ghost is not None and play.running:
                self._queue_ghost(play.ghost, ox, oy)
        for eid, body, sprite in self.world.query(Body, Sprite):
            size = (round(body.width), round(body.height))
            image = self._finished(sprite)
            lift = 0 if image is not None else self._bob(eid)
            image = image or self.art.image(sprite.current, size)
            image = self._facing(eid, image)
            _, x, y = self._at(image, (body.center_x - ox, body.bottom - oy - lift))
            x += self._tremble(eid)
            if eid in self.flashes:
                frame.sprite(flashed(image, self.flashes[eid] / HIT_FLASH), x, y)
            else:
                self._queue_lit(image, x, y)
        for _, body, interactable in self.world.query(Body, Interactable):
            if interactable.in_range:
                above = (round(body.center_x) - ox, round(body.y) - oy - 3)
                frame.sprite(*self._at(self.art.prompt, above), layer=Layer.OVERLAY)

    def _queue_lampreys(self, ox: int, oy: int) -> None:
        for eid, body, lamprey in self.world.query(Body, Lamprey):
            if (view := self.lampreys.get(eid)) is not None:
                flash = self.flashes.get(eid, 0.0) / HIT_FLASH
                view.queue(self.frame, body, lamprey, (ox, oy), flash)
                view.queue_water(self.frame, body, lamprey, (ox, oy))

    def _finished(self, sprite: Sprite) -> pygame.Surface | None:
        """The finished art for `sprite` now: its state's clip, else its looping sheet."""
        if sprite.state:
            clip = self.bank.image(f"{sprite.current}_{sprite.state}", sprite.since)
            if clip is not None:
                return clip
        return self.bank.image(sprite.current, self.clock)

    def _facing(self, eid: EntityId, image: pygame.Surface) -> pygame.Surface:
        """Placeholder art faces right; mirror it for enemies facing left."""
        brain = self.world.find(eid, Brain)
        if brain is not None and brain.facing < 0 and KINDS[brain.kind].directional:
            return pygame.transform.flip(image, True, False)
        return image

    def _tremble(self, eid: EntityId) -> int:
        """Sideways shake of a crumbling platform that is about to give way."""
        crumble = self.world.find(eid, Crumble)
        if crumble is None or crumble.state != "shaking":
            return 0
        return 1 if int(self.clock * TREMBLE_RATE) % 2 else -1

    def _bob(self, eid: EntityId) -> int:
        """A little life for placeholder enemies: walkers bob, fliers float."""
        brain = self.world.find(eid, Brain)
        if brain is None:
            return 0
        phase = self.clock + eid * FLICKER_PHASE
        if brain.kind == "wisp_eater":
            return round(math.sin(phase * 3.0) * 2)
        if brain.state in TREMBLING:
            return round(abs(math.sin(phase * 40.0)))
        return round(abs(math.sin(phase * 14.0))) if brain.state in WALKING else 0

    def _queue_lit(
        self, image: pygame.Surface, x: int, y: int, layer: Layer = Layer.ACTORS
    ) -> None:
        """Queue `image`, and its emissive pixels again on the glow layer."""
        self.frame.sprite(image, x, y, layer)
        if (glow := self.glows(image)) is not None:
            self.frame.sprite(glow, x, y, Layer.GLOW)

    @staticmethod
    def _still(eid: int, body: Body) -> tuple[int, int, int]:
        """A key for the shadows of a light that stays where it is."""
        return eid, round(body.x), round(body.y)

    def _flicker(self, eid: int) -> float:
        return self.flicker(self.clock + eid * FLICKER_PHASE)

    def _light_color(self, hex_color: str) -> tuple[int, int, int]:
        if not hex_color:
            return GLOW
        if hex_color not in self._colors:
            color = pygame.Color(hex_color)
            self._colors[hex_color] = (color.r, color.g, color.b)
        return self._colors[hex_color]

    def _ambient(self) -> tuple[int, int, int]:
        """The room's darkness, lifted toward full light by the brightness setting."""
        lift = self.ctx.settings.video.brightness * BRIGHTNESS_LIFT
        r, g, b = (round(c + (255 - c) * lift) for c in self.backdrops.ambient())
        return r, g, b

    def _draw_speech(self, canvas: pygame.Surface, ox: int, oy: int) -> None:
        keys = self.ctx.settings.controls.keys
        for speech in speeches(self.world, self.ctx.t, keys):
            self.bubbles.draw(canvas, speech.text, (speech.x - ox, speech.y - oy))

    def _draw_trial_timer(self, canvas: pygame.Surface) -> None:
        if self.trial is None:
            return
        font = self._hud_font = getattr(self, "_hud_font", None) or pygame.font.Font(None, 16)
        text = font.render(format_time(self.trial_time), False, palette.MIST)
        canvas.blit(text, text.get_rect(midtop=(canvas.get_width() // 2, 6)))

    def _draw_hud(self, canvas: pygame.Surface) -> None:
        """Health, flame, flares and embers; hidden while a cutscene plays."""
        health, ember = self.world.find(self.player, Health), self.world.find(self.player, Ember)
        if health is None or ember is None:
            return
        kit = self.world.resource(FlareKit)
        refill = kit.refill / self.feel.light.flare_refill if self.feel.light.flare_refill else 0
        state = HudState(
            health.current,
            health.max,
            ember.current,
            ember.max,
            kit.charges,
            kit.max_charges,
            refill,
            wallet(self.progress.data),
        )
        self.hud.hidden = self.cutscenes.active
        self.hud.draw(canvas, state)

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
        swing = self.world.find(self.player, Swing)
        lantern = Light(self._lantern_radius(), self.glow, light)
        self.view.queue(
            self.frame,
            self.body,
            self.motor,
            self.visual,
            swing,
            self.feel.swing,
            offset=(ox, oy),
            alpha=alpha,
            light=lantern,
        )
        if self.ghost is not None and not self.ghost.finished:
            self._queue_ghost(self.ghost, ox, oy)

    def _lantern_radius(self) -> int:
        """The lantern's glow: shrunk while guttering, swelling while kindling."""
        radius = float(GLOW_RADIUS)
        ember, kindle = self.world.find(self.player, Ember), self.world.find(self.player, Kindle)
        if ember is not None and ember.guttering:
            radius *= self.feel.light.gutter_radius
        if kindle is not None and kindle.ticks:
            radius *= 1.0 + 0.4 * kindle.progress(self.feel.light)
        return round(radius)

    def _queue_ghost(self, ghost: Ghost, ox: int, oy: int) -> None:
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
