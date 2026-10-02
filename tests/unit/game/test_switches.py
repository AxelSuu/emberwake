"""Photocells, braziers and bells on a small world."""

from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.enemies import Brain
from emberwake.game.flares import Flare
from emberwake.game.interact import Switch
from emberwake.game.light import LightSource, LightTuning
from emberwake.game.player.controller import Motor
from emberwake.game.player.swing import Direction, Strikeable
from emberwake.game.switches import (
    Bell,
    BellRung,
    Brazier,
    BrazierLit,
    Photocell,
    SwitchTuning,
    bell_system,
    brazier_system,
    photocell_system,
)

STEP = 1 / 60
TUNING = SwitchTuning(brazier_radius=60, bell_radius=50, bell_stun=2.0, bell_pulse=1.0)


class Hall:
    def __init__(self) -> None:
        self.world = World()
        self.bus = EventBus()
        self.events: list[object] = []
        for kind in (BrazierLit, BellRung):
            self.bus.subscribe(kind, self.events.append)
        for resource in (self.bus, LightTuning(lantern_radius=40), TUNING):
            self.world.insert_resource(resource)

    def add(self, *parts: object) -> EntityId:
        eid = self.world.spawn(*parts)
        self.world.flush()
        return eid

    def player(self, x: float, y: float) -> EntityId:
        return self.add(Body(x, y, 10, 20), Motor())

    def tick(self) -> None:
        for system in (brazier_system, bell_system, photocell_system):
            system(self.world, STEP)
        self.world.flush()

    def on(self, eid: EntityId) -> bool:
        return self.world.get(eid, Switch).on

    def strike(self, eid: EntityId) -> None:
        self.world.get(eid, Strikeable).struck = Direction.FORWARD


def named(*parts: object) -> list[object]:
    return [Identity("iid", "Hall", "thing"), *parts]


def cell(hall: Hall, x: float = 100, threshold: float = 0.4) -> EntityId:
    return hall.add(*named(Body(x, 100, 16, 16), Photocell(threshold), Switch()))


def brazier(hall: Hall, x: float = 100, *, lit: bool = False) -> EntityId:
    return hall.add(*named(Body(x, 100, 16, 16), Brazier(lit), Strikeable(), Switch()))


def bell(hall: Hall, x: float = 100) -> EntityId:
    return hall.add(*named(Body(x, 100, 16, 16), Bell(), Strikeable(), Switch()))


def rat(hall: Hall, x: float) -> EntityId:
    return hall.add(Body(x, 100, 16, 16), Brain("clockrat"))


def test_photocell_follows_the_light_at_it() -> None:
    hall = Hall()
    eid = cell(hall)
    hall.tick()
    assert not hall.on(eid)
    lamp = hall.add(Body(100, 100, 16, 16), LightSource(radius=60))
    hall.tick()
    assert hall.on(eid)
    hall.world.despawn(lamp)
    hall.world.flush()
    hall.tick()
    assert not hall.on(eid)


def test_photocell_needs_its_threshold() -> None:
    hall = Hall()
    eid = cell(hall, threshold=0.8)
    hall.add(Body(100 + 30, 100, 16, 16), LightSource(radius=60))
    hall.tick()
    assert not hall.on(eid)
    hall.world.get(eid, Photocell).threshold = 0.3
    hall.tick()
    assert hall.on(eid)


def test_the_lantern_lights_a_photocell() -> None:
    hall = Hall()
    eid = cell(hall)
    player = hall.player(100, 90)
    hall.tick()
    assert hall.on(eid)
    hall.world.get(player, Body).x = 300
    hall.tick()
    assert not hall.on(eid)


def test_a_photocell_with_no_light_stays_off_even_at_zero_threshold() -> None:
    hall = Hall()
    eid = cell(hall, threshold=0.0)
    hall.tick()
    assert not hall.on(eid)


def test_a_swing_lights_a_cold_brazier_once() -> None:
    hall = Hall()
    eid = brazier(hall)
    hall.tick()
    assert not hall.on(eid)
    assert hall.world.find(eid, LightSource) is None
    hall.strike(eid)
    hall.tick()
    assert hall.world.get(eid, Brazier).lit
    assert hall.on(eid)
    assert hall.world.get(eid, LightSource).radius == TUNING.brazier_radius
    hall.strike(eid)
    hall.tick()
    assert len([e for e in hall.events if isinstance(e, BrazierLit)]) == 1


def test_a_placed_lit_brazier_is_a_light_and_a_switch_without_an_event() -> None:
    hall = Hall()
    eid = brazier(hall, lit=True)
    hall.tick()
    assert hall.on(eid)
    assert hall.world.find(eid, LightSource) is not None
    assert not hall.events


def test_a_flare_touching_a_brazier_lights_it() -> None:
    hall = Hall()
    eid = brazier(hall)
    hall.add(Body(104, 104, 6, 6), Flare(), LightSource(radius=80))
    hall.tick()
    assert hall.on(eid)


def test_a_burnt_out_flare_or_a_far_one_does_not() -> None:
    hall = Hall()
    eid = brazier(hall)
    hall.add(Body(104, 104, 6, 6), Flare(), LightSource(radius=80, strength=0.0))
    hall.add(Body(160, 104, 6, 6), Flare(), LightSource(radius=80))
    hall.tick()
    assert not hall.on(eid)


def test_a_lit_brazier_lights_a_photocell() -> None:
    hall = Hall()
    eid = cell(hall, x=130)
    brazier(hall, lit=True)
    hall.tick()
    hall.tick()
    assert hall.on(eid)


def test_ringing_a_bell_stuns_enemies_in_its_radius_only() -> None:
    hall = Hall()
    ringer = bell(hall)
    near, far = rat(hall, 130), rat(hall, 200)
    hall.strike(ringer)
    hall.tick()
    assert hall.world.get(near, Brain).stagger == TUNING.bell_stun
    assert hall.world.get(far, Brain).stagger == 0
    assert len([e for e in hall.events if isinstance(e, BellRung)]) == 1


def test_a_bell_pulses_its_switch_then_goes_quiet() -> None:
    hall = Hall()
    eid = bell(hall)
    hall.tick()
    assert not hall.on(eid)
    hall.strike(eid)
    hall.tick()
    hall.world.get(eid, Strikeable).struck = None
    assert hall.on(eid)
    for _ in range(30):
        hall.tick()
    assert hall.on(eid)
    for _ in range(31):
        hall.tick()
    assert not hall.on(eid)


def test_a_second_ring_restarts_the_pulse() -> None:
    hall = Hall()
    eid = bell(hall)
    hall.strike(eid)
    hall.tick()
    hall.world.get(eid, Strikeable).struck = None
    for _ in range(40):
        hall.tick()
    hall.strike(eid)
    hall.tick()
    hall.world.get(eid, Strikeable).struck = None
    for _ in range(40):
        hall.tick()
    assert hall.on(eid)
