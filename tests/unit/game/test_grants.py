from __future__ import annotations

from pathlib import Path

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import World
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity, Spawner, WorldState
from emberwake.game.grants import (
    Grant,
    Granted,
    GrantSpec,
    Loadout,
    grant_system,
    load_grants,
)
from emberwake.game.player.controller import Motor

SPECS = {
    "flare": GrantSpec("ability"),
    "shard": GrantSpec("item", max=12),
    "oil_flask": GrantSpec("item", max=2),
    "flare_pouch": GrantSpec("item", max=4),
}


def test_abilities_are_given_once_and_items_stack_to_their_max() -> None:
    loadout = Loadout(specs=SPECS)
    assert loadout.give("flare")
    assert not loadout.give("flare")
    assert loadout.give("oil_flask", 3)
    assert loadout.count("oil_flask") == 2
    assert not loadout.give("oil_flask")
    assert not loadout.give("unknown")


def test_items_add_up_to_health_flame_and_flares() -> None:
    loadout = Loadout(specs=SPECS)
    loadout.give("shard", 5)
    loadout.give("oil_flask")
    loadout.give("flare_pouch", 2)
    assert (loadout.bonus_health, loadout.bonus_flame, loadout.bonus_flares) == (1, 20.0, 2)


def test_touching_a_grant_gives_it_and_retires_it() -> None:
    world, bus, state = World(), EventBus(), WorldState()
    granted: list[Granted] = []
    bus.subscribe(Granted, granted.append)
    loadout = Loadout(specs=SPECS)
    for resource in (bus, loadout, Spawner(world, {}, state)):
        world.insert_resource(resource)
    world.spawn(Body(0, 0, 10, 20), Motor())
    world.spawn(Body(2, 4, 16, 16), Grant("shard", 3), Identity("g1", "Room", "grant"))
    world.flush()
    grant_system(world, 1 / 60)
    world.flush()
    assert loadout.count("shard") == 3
    assert granted == [Granted("shard", 3)]
    assert state.removed == ["g1"]
    assert world.count(Grant) == 0


def test_the_shipped_grants_parse() -> None:
    specs = load_grants(Path("content/grants.toml"))
    assert specs["flare"].kind == "ability"
    assert specs["shard"].max >= 3
