"""Kindling: hold Down, standing still, to turn flame into health (docs/specs/light-rules.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body
from emberwake.game.actions import Action
from emberwake.game.combat import Health
from emberwake.game.light import Ember, LightTuning
from emberwake.game.player.controller import Motor

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

STILL = 10.0
"""Px/s of drift that still counts as standing still."""
BUSY = (Action.LEFT, Action.RIGHT, Action.JUMP, Action.DASH, Action.SWING, Action.FLARE)
"""Holding any of these interrupts kindling."""


@component
@dataclass(slots=True)
class Kindle:
    ticks: int = 0
    """Ticks Down has been held, still, toward the next heal."""

    def progress(self, tuning: LightTuning) -> float:
        """0 to 1 toward the heal, for drawing."""
        return min(self.ticks / max(tuning.kindle_ticks, 1), 1.0)


@dataclass(frozen=True, slots=True)
class Kindled:
    x: float
    y: float


def can_kindle(motor: Motor, health: Health, ember: Ember, tuning: LightTuning) -> bool:
    """Whether kindling would do anything: alive, hurt, grounded, with flame to spare."""
    return (
        not motor.dead
        and motor.grounded
        and abs(motor.vx) <= STILL
        and health.current < health.max
        and ember.current >= tuning.kindle_cost
    )


def kindle_system(world: World, dt: float) -> None:
    """Count held ticks; at `kindle_ticks` spend `kindle_cost` flame to heal 1."""
    actions, tuning = world.resource(InputState), world.resource(LightTuning)
    for eid, motor, kindle in world.query(Motor, Kindle):
        health, ember = world.find(eid, Health), world.find(eid, Ember)
        holding = actions.down(Action.DOWN) and not any(actions.down(a) for a in BUSY)
        if health is None or ember is None:
            continue
        if not holding or not can_kindle(motor, health, ember, tuning):
            kindle.ticks = 0
            continue
        kindle.ticks += 1
        if kindle.ticks >= tuning.kindle_ticks:
            kindle.ticks = 0
            ember.current -= tuning.kindle_cost
            health.current = min(health.current + 1, health.max)
            body = world.get(eid, Body)
            world.resource(EventBus).publish(Kindled(body.center_x, body.y + body.height / 2))
