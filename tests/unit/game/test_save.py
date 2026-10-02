from __future__ import annotations

from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.world.spawning import WorldState
from emberwake.game.data.save import SAVE_CODEC, SaveSlot, Stats, load_slot, save_slot, slot_key

V1 = {
    "version": 1,
    "data": {
        "room": "Lab_Lever_Hall",
        "beacon": "b-1",
        "playtime": 12.5,
        "flags": {"intro_seen": 1},
        "world": {"entities": {"l-1": {"Switch": {"on": True}}}, "removed": ["e-1"]},
        "discovered": ["r-1", "r-2"],
        "stats": {"deaths": 2, "jumps": 30, "dashes": 4, "embers": 1},
    },
}
"""A version 1 save. Keep it when bumping SAVE_CODEC: the test below proves the migration."""


def test_v1_saves_load():
    slot = SAVE_CODEC.load(V1)
    assert slot == SaveSlot(
        room="Lab_Lever_Hall",
        beacon="b-1",
        playtime=12.5,
        flags={"intro_seen": 1},
        world=WorldState({"l-1": {"Switch": {"on": True}}}, ["e-1"]),
        discovered=["r-1", "r-2"],
        stats=Stats(2, 30, 4, 1),
        abilities=["dash", "flare"],
    )


def test_round_trip_through_storage():
    storage = MemoryStorage()
    assert load_slot(storage, 2) is None
    slot = SAVE_CODEC.load(V1)
    save_slot(storage, 2, slot)
    assert slot_key(2) in storage.data
    assert load_slot(storage, 2) == slot


def test_corrupt_slots_load_as_empty_and_are_kept():
    storage = MemoryStorage()
    storage.write(slot_key(1), "{not json")
    assert load_slot(storage, 1) is None
    assert storage.read(slot_key(1) + ".corrupt") == "{not json"


def test_v1_saves_load_without_a_cinder():
    loaded = SAVE_CODEC.load(V1)
    assert loaded.cinder is None
    assert loaded.room == "Lab_Lever_Hall"


def test_new_games_start_with_only_the_dash():
    assert SaveSlot(room="Wake").abilities == ["dash"]
