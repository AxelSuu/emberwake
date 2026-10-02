from __future__ import annotations

import functools
import tomllib

from tools.levels.ldtk import build_project
from tools.levels.source import Defs, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs import Schedule, World
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.physics import Body
from emberwake.engine.world.ldtk import Project
from emberwake.engine.world.rooms import RoomGraph, RoomStreamer, WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game import paths
from emberwake.game.components import Sprite
from emberwake.game.data.save import SaveSlot
from emberwake.game.flags import Facts, admits
from emberwake.game.light import LightSource
from emberwake.game.lost_lights import LostLight, LostLightRescued, Spirit, lost_light_system
from emberwake.game.player.controller import Motor
from emberwake.game.scenes.gameplay import COLLISIONS

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
FLOOR = 9 * 16
STEP = 1 / 60


def hall(markers: str) -> str:
    return "\n".join([WALL, *[INSIDE] * 8, "#" + markers.ljust(18, ".") + "#", WALL])


ROOMS = {"A": ".l", "B": "", "C": ".....k"}
"""Three rooms in a row; the light is in A, a beacon in C."""
TOML = {
    "l": 'type = "LostLight"\nfields = { Id = "cellar" }',
    "k": 'type = "Beacon"',
}


def extras(markers: str) -> RoomFile:
    tables = [f"[entities.{m}]\n{TOML[m]}" for m in TOML if m in markers]
    return from_data(RoomFile, tomllib.loads("\n".join(tables)))


class Rig:
    """Three rooms in a row streamed in as the game does; the player is a body we move."""

    def __init__(self) -> None:
        rooms = [make_room(n, (i, 0), hall(m), extras(m)) for i, (n, m) in enumerate(ROOMS.items())]
        project = from_data(Project, build_project(Source(DEFS, rooms)))
        self.data = SaveSlot(room="A")
        self.facts = Facts(self.data.flags, self.data.abilities, self.data.inventory)
        self.world = World()
        gate = functools.partial(admits, facts=self.facts)
        self.spawner = Spawner(self.world, PREFABS, self.data.world, gate=gate)
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
        self.rescued: list[LostLightRescued] = []
        self.bus.subscribe(LostLightRescued, self.rescued.append)
        for resource in (self.facts, self.spawner, self.rooms, self.grid, self.bus):
            self.world.insert_resource(resource)
        self.rooms.enter("A")
        self.body = Body(0, FLOOR - 20, 10, 20)
        self.player = self.world.spawn(self.body, Motor())
        self.schedule = Schedule(["post"])
        self.schedule.add("post", lost_light_system)
        self.step()

    def step(self, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.schedule.run(self.world, STEP)
            self.world.flush()
        return self

    def light(self) -> tuple[Body, Spirit, Identity]:
        ((_, body, spirit, identity),) = self.world.query(Body, Spirit, Identity)
        return body, spirit, identity

    def walk_to(self, x: float, ticks: int = 1) -> Rig:
        for _ in range(ticks):
            self.body.x = x
            self.step()
        return self

    def kill(self) -> Rig:
        self.world.get(self.player, Motor).dead = True
        return self.step()


def test_a_light_waits_until_the_player_is_near():
    rig = Rig()
    body, spirit, _ = rig.light()
    home = (body.x, body.y)
    rig.walk_to(100, 30)
    assert (body.x, body.y) == home
    assert not spirit.following
    rig.walk_to(body.x, 1)
    assert spirit.following


def test_a_following_light_is_about_delay_seconds_behind():
    rig = Rig()
    body, spirit, _ = rig.light()
    start = body.x
    rig.walk_to(start)
    for tick in range(120):
        rig.walk_to(start + tick * 2)
    behind = (rig.body.x - body.x) / 2 * STEP
    assert abs(behind - spirit.delay) < 0.1


def test_a_light_follows_across_rooms_and_is_never_left_behind():
    rig = Rig()
    body, spirit, identity = rig.light()
    rig.walk_to(body.x)
    for room, x in (("B", 340), ("C", 660)):
        rig.rooms.enter(room)
        rig.walk_to(x, 10)
        assert identity.room == room
    assert "A" not in rig.rooms.loaded
    assert rig.spawner.resolve(identity.iid) is not None
    assert spirit.following


def test_leading_a_light_to_a_beacon_rescues_it_once():
    rig = Rig()
    body, _, _ = rig.light()
    rig.walk_to(body.x)
    rig.rooms.enter("B")
    rig.walk_to(340, 10)
    rig.rooms.enter("C")
    rig.walk_to(2 * 320 + 100, 60)
    assert [e.id for e in rig.rescued] == ["cellar"]
    flags = rig.data.flags
    assert flags["lost_light_cellar"] == flags["lost_lights"] == 1
    ((_, light),) = rig.world.query(LostLight)
    assert light.rescued
    assert not rig.world.has(next(iter(rig.world.query(Spirit)))[0], Sprite, LightSource)
    rig.walk_to(2 * 320 + 100, 30)
    assert flags["lost_lights"] == 1


def test_a_rescued_light_stays_rescued_when_its_room_comes_back():
    rig = Rig()
    body, _, identity = rig.light()
    rig.walk_to(body.x)
    rig.rooms.enter("B")
    rig.walk_to(340, 10)
    rig.rooms.enter("C")
    rig.walk_to(2 * 320 + 100, 60)
    rig.rooms.enter("B")
    rig.rooms.enter("A")
    room = rig.rooms.loaded["A"]
    rig.spawner.despawn_room(room)
    rig.step()
    assert rig.data.world.entities[identity.iid]["LostLight"] == {"rescued": True}
    rig.spawner.spawn_room(room)
    rig.step(2)
    ((eid, light),) = rig.world.query(LostLight)
    assert light.rescued
    assert not rig.world.has(eid, Sprite)


def test_dying_sends_a_following_light_home_to_be_led_again():
    rig = Rig()
    body, spirit, identity = rig.light()
    home = (body.x, body.y)
    rig.walk_to(body.x)
    rig.walk_to(body.x + 150, 60)
    rig.rooms.enter("B")
    rig.walk_to(400, 5)
    assert identity.room == "B"
    rig.kill()
    assert (body.x, body.y) == home
    assert identity.room == "A"
    assert not spirit.following
    assert rig.data.flags == {}
