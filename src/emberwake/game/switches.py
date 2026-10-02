"""Light-driven signal sources: photocells, ignitable braziers and bells.

All three carry a `Switch`, so doors read them through the signal system like levers. A brazier
lit by a swing or a flare keeps its state in `WorldState` by iid; see docs/specs/light-switches.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body
from emberwake.game.enemies import Brain
from emberwake.game.flares import Flare
from emberwake.game.interact import Switch, overlap, set_switch
from emberwake.game.light import LightSource, light_at
from emberwake.game.player.swing import Strikeable

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

BRAZIER_COLOR = "#fb6b1d"


@dataclass(frozen=True, slots=True)
class SwitchTuning:
    """Numbers for braziers and bells (content/feel.toml, ``[switches]``): px and seconds."""

    brazier_radius: float = 72.0
    bell_radius: float = 80.0
    bell_stun: float = 2.0
    bell_pulse: float = 1.5
    """Seconds a bell's signal stays on after a ring."""
    bell_trauma: float = 0.15


@component
@dataclass(slots=True)
class Photocell:
    """On while the light at its centre reaches `threshold`."""

    threshold: float = 0.4


@component
@dataclass(slots=True)
class Brazier:
    """Cold until struck or touched by a flare, then a light and an on switch for good."""

    lit: bool = False


@component
@dataclass(slots=True)
class Bell:
    """Rung by a swing: an on switch for a while, and it stuns enemies nearby."""

    pulse: float = 0.0
    """Seconds its signal has left."""


@dataclass(frozen=True, slots=True)
class BrazierLit:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class BellRung:
    x: float
    y: float


def photocell_system(world: World, dt: float) -> None:
    """Switch every photocell on or off by the light at it."""
    for eid, body, cell, switch in world.query(Body, Photocell, Switch):
        light = light_at(world, body.center_x, body.y + body.height / 2)
        set_switch(world, eid, switch, light > 0 and light >= cell.threshold)


def brazier_system(world: World, dt: float) -> None:
    """Light cold braziers a swing or a flare reaches; lit ones are lights and on switches."""
    tuning, bus = world.resource(SwitchTuning), world.resource(EventBus)
    flares = [body for _, body, _, light in world.query(Body, Flare, LightSource) if light.strength]
    for eid, body, brazier, switch in world.query(Body, Brazier, Switch):
        if not brazier.lit:
            strikeable = world.find(eid, Strikeable)
            struck = strikeable is not None and strikeable.struck is not None
            if struck or any(overlap(body, flare) for flare in flares):
                brazier.lit = True
                bus.publish(BrazierLit(body.center_x, body.y + body.height / 2))
        if brazier.lit and world.find(eid, LightSource) is None:
            world.add(eid, LightSource(radius=tuning.brazier_radius, color=BRAZIER_COLOR))
        set_switch(world, eid, switch, brazier.lit)


def bell_system(world: World, dt: float) -> None:
    """A struck bell stuns the enemies in its radius and pulses its switch."""
    tuning, bus = world.resource(SwitchTuning), world.resource(EventBus)
    for eid, body, bell, switch in world.query(Body, Bell, Switch):
        strikeable = world.find(eid, Strikeable)
        if strikeable is not None and strikeable.struck is not None:
            bell.pulse = tuning.bell_pulse
            x, y = body.center_x, body.y + body.height / 2
            _stun(world, x, y, tuning)
            bus.publish(BellRung(x, y))
        else:
            bell.pulse = max(bell.pulse - dt, 0.0)
        set_switch(world, eid, switch, bell.pulse > 0)


def _stun(world: World, x: float, y: float, tuning: SwitchTuning) -> None:
    for _, body, brain in world.query(Body, Brain):
        if math.hypot(body.center_x - x, body.y + body.height / 2 - y) <= tuning.bell_radius:
            brain.stagger = max(brain.stagger, tuning.bell_stun)
            brain.push = (0.0, 0.0)
