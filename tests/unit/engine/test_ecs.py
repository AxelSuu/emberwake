from __future__ import annotations

import doctest
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from emberwake.engine import ecs
from emberwake.engine.ecs import EntityId, Registry, Schedule, World
from emberwake.engine.ecs import registry as registry_module
from emberwake.engine.ecs import schedule as schedule_module
from emberwake.engine.ecs import world as world_module

if TYPE_CHECKING:
    from types import ModuleType


@dataclass(slots=True)
class Pos:
    x: float = 0.0


@dataclass(slots=True)
class Vel:
    dx: float = 0.0


@dataclass(slots=True)
class Tag:
    pass


@dataclass(slots=True)
class Hp:
    hp: int = 3


def spawned(world: World, *components: object) -> EntityId:
    eid = world.spawn(*components)
    world.flush()
    return eid


@pytest.mark.parametrize("module", [world_module, schedule_module, registry_module])
def test_docstring_examples(module: ModuleType):
    assert doctest.testmod(module).failed == 0


def test_spawn_is_deferred_until_flush():
    world = World()
    eid = world.spawn(Pos(1))
    assert eid not in world
    assert world.find(eid, Pos) is None
    world.flush()
    assert eid in world
    assert world.get(eid, Pos) == Pos(1)
    assert len(world) == 1


def test_ids_are_unique_and_never_reused():
    world = World()
    a = spawned(world)
    world.despawn(a)
    world.flush()
    assert spawned(world) != a


def test_add_replaces_and_remove_detaches():
    world = World()
    eid = spawned(world, Pos(1))
    world.add(eid, Pos(2), Vel(3))
    world.remove(eid, Tag)
    world.flush()
    assert world.get(eid, Pos) == Pos(2)
    assert world.has(eid, Pos, Vel)
    world.remove(eid, Vel)
    world.flush()
    assert not world.has(eid, Vel)
    assert world.has(eid, Pos)


def test_despawn_drops_components_and_later_changes():
    world = World()
    eid = spawned(world, Pos(), Vel())
    world.despawn(eid)
    world.add(eid, Tag())
    world.flush()
    assert eid not in world
    assert world.count(Pos) == world.count(Vel) == world.count(Tag) == 0
    with pytest.raises(KeyError):
        world.get(eid, Pos)


def test_changes_apply_in_order():
    world = World()
    eid = world.spawn(Pos(1))
    world.add(eid, Pos(2))
    world.remove(eid, Pos)
    world.add(eid, Pos(3))
    world.flush()
    assert world.get(eid, Pos) == Pos(3)


def test_query_matches_entities_with_every_type():
    world = World()
    a = world.spawn(Pos(1), Vel(1), Tag(), Hp())
    b = world.spawn(Pos(2), Vel(2))
    c = world.spawn(Pos(3))
    world.spawn(Vel(4), Tag())
    world.flush()
    assert [eid for eid, _ in world.query(Pos)] == [a, b, c]
    assert list(world.query(Pos, Vel)) == [(a, Pos(1), Vel(1)), (b, Pos(2), Vel(2))]
    assert list(world.query(Vel, Pos)) == [(a, Vel(1), Pos(1)), (b, Vel(2), Pos(2))]
    assert list(world.query(Pos, Vel, Tag)) == [(a, Pos(1), Vel(1), Tag())]
    assert list(world.query(Pos, Vel, Tag, Hp)) == [(a, Pos(1), Vel(1), Tag(), Hp())]
    assert list(world.query(Hp, Pos, Vel, Tag)) == [(a, Hp(), Pos(1), Vel(1), Tag())]


def test_query_of_missing_type_is_empty():
    world = World()
    eid = spawned(world, Pos())
    assert list(world.query(Pos, Tag)) == []
    world.remove(eid, Pos)
    world.flush()
    assert list(world.query(Pos)) == []


def test_spawning_while_iterating_is_safe():
    world = World()
    spawned(world, Pos())
    for _, pos in world.query(Pos):
        world.spawn(Pos(pos.x + 1))
    world.flush()
    assert world.count(Pos) == 2


def test_resources():
    world = World()
    world.insert_resource(Hp(5))
    world.insert_resource(Pos(1), key=Vel)
    assert world.resource(Hp) == Hp(5)
    assert world.resource(Vel) == Pos(1)
    assert world.has_resource(Vel)
    assert not world.has_resource(Pos)
    with pytest.raises(KeyError):
        world.resource(Pos)


def test_schedule_runs_phases_in_order_and_flushes_between():
    world = World()
    seen: list[str] = []

    def spawn(w: World, _: float) -> None:
        w.spawn(Pos())
        seen.append(f"spawn {w.count(Pos)}")

    def look(w: World, _: float) -> None:
        seen.append(f"look {w.count(Pos)}")

    schedule = Schedule(["a", "b"])
    schedule.add("b", look)
    schedule.add("a", spawn)
    schedule.add("a", look)
    schedule.run(world, 0.0)
    assert seen == ["spawn 0", "look 0", "look 1"]
    assert schedule.phases == ("a", "b")


def test_schedule_flushes_before_first_phase_and_after_last():
    world = World()
    eid = world.spawn(Pos())
    schedule = Schedule(["only"])
    schedule.add("only", lambda w, _: w.despawn(eid))
    found: list[bool] = []
    schedule.add("only", lambda w, _: found.append(eid in w))
    schedule.run(world, 0.0)
    assert found == [True]
    assert eid not in world


def test_schedule_rejects_unknown_phase():
    with pytest.raises(KeyError, match="unknown phase"):
        Schedule(["a"]).add("b", lambda w, dt: None)


def test_registry_by_name():
    registry = Registry()
    registry.register(Pos)
    assert registry.register(Pos) is Pos
    assert registry["Pos"] is Pos
    assert "Pos" in registry
    assert list(registry) == ["Pos"]
    with pytest.raises(KeyError, match="unknown component"):
        registry["Vel"]


def test_registry_rejects_name_clash_and_non_dataclasses():
    registry = Registry()
    registry.register(Pos)

    @dataclass
    class Pos2:
        pass

    Pos2.__name__ = "Pos"
    with pytest.raises(ValueError, match="taken"):
        registry.register(Pos2)
    with pytest.raises(TypeError, match="dataclass"):
        registry.register(int)


def test_component_decorator_uses_the_shared_registry():
    @ecs.component
    @dataclass(slots=True)
    class EcsTestMarker:
        pass

    assert ecs.COMPONENTS["EcsTestMarker"] is EcsTestMarker
