from __future__ import annotations

import functools
import tomllib

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import EntityId, Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.physics import Body, Tile
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import RoomGraph, RoomStreamer, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner, WorldState
from emberwake.game import paths
from emberwake.game.combat import Health
from emberwake.game.data.save import SaveSlot
from emberwake.game.encounters import (
    Encounter,
    EncounterCleared,
    EncounterStarted,
    EncounterTuning,
    encounter_system,
    lock_system,
)
from emberwake.game.enemies import Brain, EnemyTuning, Minion, enemy_system
from emberwake.game.flags import Facts, admits
from emberwake.game.interact import Switch
from emberwake.game.light import LightTuning
from emberwake.game.player.controller import Motor
from emberwake.game.scenes.gameplay import COLLISIONS
from emberwake.game.signals import Wiring, door_system, signal_system

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
STEP = 1 / 60
WALL = "#" * 20
HALL = "\n".join(
    [
        WALL,
        *["#..d" + "Z" * 14 + "##"] * 5,
        *["#..d" + "Z" * 14 + "o#"] * 3,
        "#.Pd.r.a..b..K.r..o#",
        WALL,
    ]
)
TOML = """
[entities.Z]
type = "Encounter"
fields = { Doors = ["d"], Targets = ["o"] }
[entities.d]
type = "Door"
[entities.o]
type = "Door"
[entities.a]
type = "WaveSpawn"
fields = { Encounter = "Z", Wave = 1, Kind = "clockrat" }
[entities.b]
type = "WaveSpawn"
fields = { Encounter = "Z", Wave = 1, Kind = "gearbug" }
[entities.K]
type = "WaveSpawn"
fields = { Encounter = "Z", Wave = 2, Kind = "clockrat_king" }
[entities.r]
type = "RatSpawn"
"""
FEET = 10 * 16
OUTSIDE, INSIDE = 1 * 16 + 3, 6 * 16 + 3
TUNING = EncounterTuning()


class Rig:
    """One hall streamed in, with the systems an encounter touches."""

    def __init__(self, state: WorldState | None = None, toml: str = TOML) -> None:
        hall = make_room("Hall", (0, 0), HALL, from_data(RoomFile, tomllib.loads(toml)))
        project = from_data(Project, build_project(Source(DEFS, [hall])))
        data = SaveSlot(room="Hall", world=state or WorldState())
        self.data = data
        self.world = World()
        self.facts = Facts(data.flags, data.abilities, data.inventory)
        gate = functools.partial(admits, facts=self.facts)
        self.spawner = Spawner(self.world, PREFABS, data.world, gate=gate)
        self.grid = WorldGrid()
        self.rooms = RoomStreamer(
            RoomGraph(project.levels),
            self.grid,
            "Collisions",
            COLLISIONS,
            on_load=self.spawner.spawn_room,
            on_unload=self.spawner.despawn_room,
        )
        self.bus = EventBus()
        self.started: list[EncounterStarted] = []
        self.cleared_events: list[EncounterCleared] = []
        self.bus.subscribe(EncounterStarted, self.started.append)
        self.bus.subscribe(EncounterCleared, self.cleared_events.append)
        wiring = Wiring.from_levels(project.levels, PREFABS)
        for resource in (self.facts, self.spawner, self.rooms, wiring, self.bus, TUNING):
            self.world.insert_resource(resource)
        for resource in (EnemyTuning(), LightTuning()):
            self.world.insert_resource(resource)
        self.world.insert_resource(self.grid)
        self.rooms.enter("Hall")
        self.body = Body(OUTSIDE, FEET - 20, 10, 20)
        self.motor = Motor()
        self.player = self.world.spawn(self.body, self.motor)
        self.schedule = Schedule(["logic", "post"])
        self.schedule.add("logic", enemy_system)
        for system in (encounter_system, signal_system, lock_system, door_system):
            self.schedule.add("post", system)
        self.step()

    def step(self, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.schedule.run(self.world, STEP)
        return self

    def seconds(self, seconds: float) -> Rig:
        return self.step(round(seconds / STEP))

    def enter(self) -> Rig:
        self.body.x = INSIDE
        return self.step(2)

    def leave(self) -> Rig:
        self.body.x = OUTSIDE
        return self

    def encounter_id(self) -> EntityId:
        ((eid, _),) = self.world.query(Encounter)
        return eid

    def enemies(self, kind: str | None = None) -> list[EntityId]:
        """The wave's enemies, owned by the encounter."""
        owner = self.encounter_id()
        return sorted(
            eid
            for eid, brain, minion in self.world.query(Brain, Minion)
            if minion.owner == owner and (kind is None or brain.kind == kind)
        )

    def rats_of(self, king: EntityId) -> list[EntityId]:
        return sorted(e for e, b, m in self.world.query(Brain, Minion) if m.owner == king)

    def kill(self, *enemies: EntityId) -> Rig:
        for eid in enemies:
            self.world.get(eid, Health).dead = True
        return self.step(2)

    def encounter(self) -> Encounter:
        return self.world.get(self.encounter_id(), Encounter)

    def cleared(self) -> bool:
        return self.world.get(self.encounter_id(), Switch).on

    def shut(self, column: int, row: int) -> bool:
        return self.grid.get(column, row) == Tile.SOLID

    def next_wave(self) -> Rig:
        return self.seconds(TUNING.wave_delay + 0.1)


def test_stepping_into_the_zone_shuts_the_door_and_sends_wave_one() -> None:
    rig = Rig()
    assert not rig.enemies()
    assert not rig.shut(3, 4)
    rig.enter()
    assert rig.started
    assert rig.encounter().active
    assert sorted(rig.world.get(e, Brain).kind for e in rig.enemies()) == ["clockrat", "gearbug"]
    assert rig.shut(3, 4)
    assert rig.shut(18, 7)


def test_a_wave_enemy_stands_on_its_marker_and_is_not_a_placed_enemy() -> None:
    rig = Rig().enter()
    (rat,) = rig.enemies("clockrat")
    body = rig.world.get(rat, Body)
    assert (body.center_x, body.bottom) == (7 * 16 + 8, FEET)
    assert rig.world.get(rat, Identity).iid.endswith(":wave")


def test_the_next_wave_comes_after_the_delay_and_not_before() -> None:
    rig = Rig().enter()
    rig.kill(*rig.enemies())
    assert not rig.enemies()
    rig.seconds(TUNING.wave_delay / 2)
    assert not rig.enemies()
    rig.next_wave()
    assert [rig.world.get(e, Brain).kind for e in rig.enemies()] == ["clockrat_king"]
    assert rig.encounter().wave == 2
    assert not rig.cleared()


def test_the_last_wave_dying_clears_it_opens_the_doors_and_powers_the_targets() -> None:
    rig = Rig().enter()
    rig.kill(*rig.enemies()).next_wave()
    assert rig.shut(3, 4)
    assert rig.shut(18, 7)
    rig.kill(*rig.enemies())
    assert rig.cleared()
    assert len(rig.cleared_events) == 1
    assert not rig.encounter().active
    assert not rig.shut(3, 4)
    assert not rig.shut(18, 7)


def test_a_wave_king_is_not_retired_and_takes_its_rats_with_it() -> None:
    rig = Rig().enter()
    rig.kill(*rig.enemies()).next_wave()
    (king,) = rig.enemies("clockrat_king")
    rig.world.get(king, Brain).state = "call"
    rig.seconds(1.5)
    rats = rig.rats_of(king)
    assert rats
    assert rig.enemies() == [king]
    rig.kill(king)
    assert rig.cleared()
    assert not list(rig.world.query(Brain))
    assert not rig.data.world.removed


def test_dying_mid_fight_resets_it() -> None:
    rig = Rig().enter()
    rig.motor.dead = True
    rig.step(2)
    assert not rig.enemies()
    assert not rig.encounter().active
    assert not rig.shut(3, 4)
    assert not rig.cleared()
    rig.motor.dead = False
    rig.enter()
    assert len(rig.enemies()) == 2
    assert len(rig.started) == 2


def test_staying_out_of_the_zone_resets_it_after_the_grace() -> None:
    rig = Rig().enter()
    rig.leave().seconds(TUNING.leave_grace / 2)
    assert rig.encounter().active
    rig.enter().seconds(TUNING.leave_grace)
    assert rig.encounter().active
    rig.leave().seconds(TUNING.leave_grace + 0.2)
    assert not rig.encounter().active
    assert not rig.enemies()
    assert not rig.shut(3, 4)


def test_unloading_the_room_mid_fight_takes_the_wave_with_it() -> None:
    rig = Rig().enter()
    assert rig.enemies()
    rig.spawner.despawn_room(rig.rooms.loaded["Hall"])
    rig.world.flush()
    assert not list(rig.world.query(Brain))


def test_a_cleared_encounter_stays_cleared_in_the_saved_world() -> None:
    rig = Rig().enter()
    rig.kill(*rig.enemies()).next_wave()
    rig.kill(*rig.enemies())
    assert rig.cleared()
    rig.spawner.snapshot_all()
    again = Rig(rig.data.world)
    assert again.cleared()
    assert not again.shut(18, 7)
    again.enter()
    assert not list(again.world.query(Brain))
    assert not again.started
    assert not [iid for iid in again.data.world.removed if iid.endswith(":wave")]


def test_a_reset_encounter_is_saved_as_not_cleared() -> None:
    rig = Rig().enter()
    rig.motor.dead = True
    rig.step(2)
    rig.spawner.snapshot_all()
    assert not Rig(rig.data.world).cleared()
