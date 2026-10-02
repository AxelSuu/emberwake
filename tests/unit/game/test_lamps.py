"""Lamps: lit by a Struck, held by a lit beacon, put out by snuff; Wisp-eaters hunt them."""

from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity, Spawner, WorldState
from emberwake.game.beacons import Beacon
from emberwake.game.lamps import (
    Lamp,
    LampLit,
    LampSnuffed,
    LampTuning,
    Shelter,
    lamp_system,
    nearest_prey,
    snuff,
)
from emberwake.game.light import LightSource, LightTuning, light_at
from emberwake.game.player.swing import Direction, Strikeable

STEP = 1 / 60


class Street:
    def __init__(self) -> None:
        self.world = World()
        self.state = WorldState()
        self.bus = EventBus()
        self.lit: list[LampLit] = []
        self.out: list[LampSnuffed] = []
        self.bus.subscribe(LampLit, self.lit.append)
        self.bus.subscribe(LampSnuffed, self.out.append)
        spawner = Spawner(self.world, {}, self.state)
        for resource in (self.bus, LampTuning(), LightTuning(), spawner):
            self.world.insert_resource(resource)
        self.spawner = spawner

    def lamp(
        self, iid: str = "l1", x: float = 100, *, beacon: str = "", **fields: bool
    ) -> EntityId:
        eid = self.world.spawn(
            Body(x, 100, 16, 32),
            Identity(iid, "Room", "lamp"),
            Lamp(**fields),
            Strikeable(),
            Shelter(beacon),
        )
        self.world.flush()
        return eid

    def beacon(self, iid: str = "b1", *, lit: bool = True) -> EntityId:
        eid = self.world.spawn(Body(0, 100, 16, 16), Identity(iid, "Room", "beacon"), Beacon(lit))
        self.spawner.ids[iid] = eid
        self.world.flush()
        return eid

    def strike(self, eid: EntityId) -> None:
        self.world.get(eid, Strikeable).struck = Direction.FORWARD

    def tick(self) -> None:
        lamp_system(self.world, STEP)
        self.world.flush()

    def get(self, eid: EntityId) -> Lamp:
        return self.world.get(eid, Lamp)


def test_a_struck_lamp_lights_and_gives_light() -> None:
    street = Street()
    lamp = street.lamp()
    street.tick()
    assert not street.get(lamp).lit
    assert not street.world.has(lamp, LightSource)
    assert light_at(street.world, 108, 116, lantern=False) == 0
    street.strike(lamp)
    street.tick()
    assert street.get(lamp).lit
    assert street.world.get(lamp, LightSource).radius == LampTuning().radius
    assert light_at(street.world, 108, 116, lantern=False) > 0.9
    assert street.lit == [LampLit("l1", 108, 116)]


def test_striking_a_lit_lamp_does_nothing_more() -> None:
    street = Street()
    lamp = street.lamp(lit=True)
    street.strike(lamp)
    street.tick()
    street.tick()
    assert street.lit == []
    assert street.get(lamp).lit


def test_a_lamp_that_is_lit_when_it_spawns_is_a_light_source() -> None:
    street = Street()
    lamp = street.lamp(lit=True)
    street.tick()
    assert street.world.has(lamp, LightSource)


def test_a_beacon_holds_lit_lamps_whichever_was_lit_first() -> None:
    street = Street()
    beacon = street.beacon(lit=False)
    first, second = street.lamp("l1", beacon="b1"), street.lamp("l2", 200, beacon="b1")
    street.strike(first)
    street.tick()
    assert not street.get(first).protected
    street.world.get(beacon, Beacon).lit = True
    street.tick()
    assert street.get(first).protected
    assert not street.get(second).protected
    street.strike(second)
    street.tick()
    assert street.get(second).protected


def test_a_beacon_in_an_unloaded_room_holds_too() -> None:
    street = Street()
    street.state.entities["far"] = {"Beacon": {"lit": True}}
    lamp = street.lamp(beacon="far", lit=True)
    street.tick()
    assert street.get(lamp).protected


def test_lamps_without_a_lit_beacon_stay_unprotected() -> None:
    street = Street()
    street.beacon(lit=False)
    loose = street.lamp("l1", lit=True)
    waiting = street.lamp("l2", beacon="b1", lit=True)
    missing = street.lamp("l3", beacon="nowhere", lit=True)
    street.tick()
    assert not any(street.get(lamp).protected for lamp in (loose, waiting, missing))


def test_a_dark_lamp_is_not_protected_by_a_lit_beacon() -> None:
    street = Street()
    street.beacon()
    lamp = street.lamp(beacon="b1")
    street.tick()
    assert not street.get(lamp).protected


def test_snuff_puts_out_a_lit_unprotected_lamp() -> None:
    street = Street()
    lamp = street.lamp(lit=True)
    street.tick()
    assert snuff(street.world, lamp)
    street.tick()
    assert not street.get(lamp).lit
    assert not street.world.has(lamp, LightSource)
    assert street.out == [LampSnuffed("l1", 108, 116)]
    assert not snuff(street.world, lamp)
    assert len(street.out) == 1


def test_snuff_leaves_protected_lamps_alone() -> None:
    street = Street()
    street.beacon()
    lamp = street.lamp(beacon="b1", lit=True)
    street.tick()
    assert not snuff(street.world, lamp)
    assert street.get(lamp).lit
    assert street.out == []


def test_nearest_prey_is_the_nearest_lit_unprotected_lamp_in_range() -> None:
    street = Street()
    street.lamp("dark", 110)
    street.lamp("safe", 120, lit=True, protected=True)
    near = street.lamp("near", 150, lit=True)
    far = street.lamp("far", 250, lit=True)
    world = street.world
    assert nearest_prey(world, 100, 116, 200) == near
    assert nearest_prey(world, 300, 116, 100) == far
    assert nearest_prey(world, 100, 116, 20) is None
