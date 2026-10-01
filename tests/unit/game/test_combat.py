from __future__ import annotations

import pytest

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.physics import Body
from emberwake.game import components  # noqa: F401
from emberwake.game.combat import (
    Damaged,
    Health,
    Hitbox,
    Hurtbox,
    Killed,
    Knockback,
    Team,
    combat_system,
)


class Arena:
    def __init__(self) -> None:
        self.world = World()
        self.bus = EventBus()
        self.world.insert_resource(self.bus)
        self.damaged: list[Damaged] = []
        self.killed: list[Killed] = []
        self.bus.subscribe(Damaged, self.damaged.append)
        self.bus.subscribe(Killed, self.killed.append)

    def attacker(self, x: float = 0, **hitbox: object) -> EntityId:
        box = Hitbox(offset=(16, 0), size=(16, 16), **hitbox)  # ty: ignore[invalid-argument-type]
        box.activate()
        eid = self.world.spawn(Body(x, 0, 16, 16), box)
        self.world.flush()
        return eid

    def enemy(self, x: float, team: Team = Team.ENEMY, **health: object) -> EntityId:
        eid = self.world.spawn(
            Body(x, 0, 16, 16),
            Health(**health),  # ty: ignore[invalid-argument-type]
            Hurtbox(team),
        )
        self.world.flush()
        return eid

    def tick(self, dt: float = 1 / 60) -> None:
        self.world.flush()
        combat_system(self.world, dt)
        self.world.flush()


def test_a_hit_damages_and_reports() -> None:
    a = Arena()
    attacker, target = a.attacker(), a.enemy(16)
    a.tick()
    assert a.world.get(target, Health).current == 2
    event = a.damaged[0]
    assert (event.target, event.attacker, event.amount, event.health) == (target, attacker, 1, 2)


def test_a_miss_does_nothing() -> None:
    a = Arena()
    a.attacker()
    a.enemy(80)
    a.tick()
    assert not a.damaged


def test_layers_decide_who_can_be_hit() -> None:
    a = Arena()
    a.attacker(targets=Team.ENEMY)
    friend = a.enemy(16, Team.PLAYER)
    a.tick()
    assert not a.damaged
    assert a.world.get(friend, Health).current == 3


def test_a_mask_can_target_several_layers() -> None:
    a = Arena()
    a.attacker(targets=Team.ENEMY | Team.PLAYER)
    a.enemy(16, Team.PLAYER)
    a.tick()
    assert len(a.damaged) == 1


def test_one_swing_hurts_once_and_a_new_swing_hurts_again_after_iframes() -> None:
    a = Arena()
    attacker = a.attacker()
    target = a.enemy(16, iframes=0.1)
    for _ in range(5):
        a.tick()
    assert len(a.damaged) == 1
    for _ in range(10):
        a.tick()
    assert len(a.damaged) == 1
    a.world.get(attacker, Hitbox).activate()
    a.tick()
    assert len(a.damaged) == 2
    assert a.world.get(target, Health).current == 1


def test_iframes_block_a_second_attacker() -> None:
    a = Arena()
    a.attacker()
    a.attacker()
    a.enemy(16, iframes=1.0)
    a.tick()
    assert len(a.damaged) == 1


def test_inactive_hitboxes_do_not_hit() -> None:
    a = Arena()
    attacker = a.attacker()
    a.world.get(attacker, Hitbox).deactivate()
    a.enemy(16)
    a.tick()
    assert not a.damaged


def test_death_is_reported_once_and_dead_things_stay_unhurt() -> None:
    a = Arena()
    attacker = a.attacker(damage=5)
    target = a.enemy(16, max=3, iframes=0.0)
    a.tick()
    assert a.world.get(target, Health).dead
    assert a.world.get(target, Health).current == 0
    assert len(a.killed) == 1
    a.world.get(attacker, Hitbox).activate()
    a.tick()
    assert len(a.killed) == 1
    assert len(a.damaged) == 1


def test_knockback_pushes_away_from_the_attacker_and_up() -> None:
    a = Arena()
    a.attacker(x=0, knockback=100.0)
    right = a.enemy(16)
    a.tick()
    push = a.world.get(right, Knockback)
    assert push.vx == 100
    assert push.vy == pytest.approx(-40)
    left = Arena()
    left.attacker(x=40, knockback=100.0, flip=True)
    target = left.enemy(24)
    left.tick()
    assert left.world.get(target, Knockback).vx == -100


def test_an_entity_never_hits_itself() -> None:
    a = Arena()
    box = Hitbox(offset=(0, 0), size=(16, 16), targets=Team.ALL)
    box.activate()
    a.world.spawn(Body(0, 0, 16, 16), box, Health(), Hurtbox(Team.ENEMY))
    a.tick()
    assert not a.damaged


def test_flip_mirrors_the_hitbox() -> None:
    box = Hitbox(offset=(16, 0), size=(8, 8), flip=True)
    area = box.area(Body(100, 50, 16, 16))
    assert (area.x, area.y) == (92, 50)
    assert box.area(Body(100, 50, 16, 16)).width == 8


def test_invulnerability_counts_down() -> None:
    a = Arena()
    target = a.enemy(200, iframes=0.5)
    a.world.get(target, Health).invulnerable = 0.5
    a.tick(0.3)
    assert a.world.get(target, Health).invulnerable == pytest.approx(0.2)
    a.tick(1.0)
    assert a.world.get(target, Health).invulnerable == 0
