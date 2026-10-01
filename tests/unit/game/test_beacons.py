"""Relighting a beacon is a rest: health, dash and a save request."""

from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import World
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.beacons import Beacon, BeaconLit, Rested, beacon_system
from emberwake.game.combat import Health
from emberwake.game.interact import Interactable
from emberwake.game.player.controller import Motor
from emberwake.game.player.tuning import PlayerTuning


def test_using_a_beacon_lights_it_heals_and_rests() -> None:
    world, bus = World(), EventBus()
    events: list[object] = []
    bus.subscribe(Rested, events.append)
    bus.subscribe(BeaconLit, events.append)
    world.insert_resource(bus)
    world.insert_resource(PlayerTuning())
    player = world.spawn(Body(0, 0, 10, 20), Motor(dash_charges=0), Health(5, current=2))
    beacon = world.spawn(
        Body(0, 0, 16, 16), Interactable(used=True), Beacon(), Identity("b1", "Room", "beacon")
    )
    world.flush()
    beacon_system(world, 1 / 60)
    assert world.get(beacon, Beacon).lit
    assert world.get(player, Health).current == 5
    assert world.get(player, Motor).dash_charges == PlayerTuning().dash_charges
    assert [type(event) for event in events] == [Rested, BeaconLit]
