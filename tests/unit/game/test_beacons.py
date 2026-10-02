"""Relighting a beacon is a rest: health, dash and a save request."""

from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import World
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.beacons import Beacon, BeaconFlag, BeaconLit, Rested, beacon_system
from emberwake.game.combat import Health
from emberwake.game.flags import Facts
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


def test_a_beacon_with_a_flag_sets_it_when_lit() -> None:
    world, flags = World(), dict[str, int]()
    world.insert_resource(EventBus())
    world.insert_resource(PlayerTuning())
    world.insert_resource(Facts(flags, [], {}))
    world.spawn(
        Body(0, 0, 16, 16),
        Interactable(used=True),
        Beacon(),
        BeaconFlag("lamp_b"),
        Identity("b1", "Room", "beacon"),
    )
    world.flush()
    beacon_system(world, 1 / 60)
    assert flags == {"lamp_b": 1}
