"""Kindling: hold Down, still, to turn flame into health."""

from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import World
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body
from emberwake.game.actions import Action
from emberwake.game.combat import Health
from emberwake.game.light import Ember, LightTuning
from emberwake.game.player.controller import Motor
from emberwake.game.player.kindle import Kindle, Kindled, kindle_system

TUNING = LightTuning(kindle_ticks=10, kindle_cost=30)


class Player:
    def __init__(self, flame: float = 100, hp: int = 1) -> None:
        self.world = World()
        self.actions = InputState[Action]()
        self.bus = EventBus()
        self.kindled: list[Kindled] = []
        self.bus.subscribe(Kindled, self.kindled.append)
        for resource in (self.actions, self.bus, TUNING):
            self.world.insert_resource(resource)
        self.eid = self.world.spawn(
            Body(0, 0, 10, 20), Motor(grounded=True), Health(3, current=hp), Ember(flame), Kindle()
        )
        self.world.flush()

    def hold(self, *actions: Action, ticks: int = 1) -> None:
        for _ in range(ticks):
            self.actions.advance(frozenset(actions))
            kindle_system(self.world, 1 / 60)

    @property
    def health(self) -> Health:
        return self.world.get(self.eid, Health)

    @property
    def flame(self) -> float:
        return self.world.get(self.eid, Ember).current


def test_holding_down_still_heals_one_for_flame() -> None:
    player = Player()
    player.hold(Action.DOWN, ticks=TUNING.kindle_ticks - 1)
    assert player.health.current == 1
    player.hold(Action.DOWN)
    assert player.health.current == 2
    assert player.flame == 70
    assert len(player.kindled) == 1


def test_moving_or_letting_go_starts_over() -> None:
    player = Player()
    player.hold(Action.DOWN, ticks=TUNING.kindle_ticks - 2)
    player.hold(Action.DOWN, Action.RIGHT)
    player.hold(Action.DOWN, ticks=TUNING.kindle_ticks - 1)
    assert player.health.current == 1


def test_no_kindling_without_flame_to_spare_or_at_full_health() -> None:
    poor = Player(flame=20)
    poor.hold(Action.DOWN, ticks=TUNING.kindle_ticks * 2)
    assert poor.health.current == 1
    whole = Player(hp=3)
    whole.hold(Action.DOWN, ticks=TUNING.kindle_ticks * 2)
    assert whole.flame == 100


def test_kindling_needs_the_ground() -> None:
    player = Player()
    player.world.get(player.eid, Motor).grounded = False
    player.hold(Action.DOWN, ticks=TUNING.kindle_ticks * 2)
    assert player.health.current == 1
