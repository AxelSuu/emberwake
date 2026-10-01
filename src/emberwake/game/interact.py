"""What the player touches or uses: triggers, interactables, switches, plates and pickups."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game.actions import Action
from emberwake.game.player.controller import Motor

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId, World


@component
@dataclass(slots=True)
class Trigger:
    """Tracks whether the player overlaps the entity's body."""

    inside: bool = False


@component
@dataclass(slots=True)
class Interactable:
    prompt: str = "use"
    reach: float = 6.0
    """How far around the body the player can be, in px."""
    in_range: bool = False
    """This is the interactable the player would use now."""


@component
@dataclass(slots=True)
class Switch:
    targets: list[str] = field(default_factory=list)
    """Iids of the receivers it powers."""
    mode: Literal["toggle", "momentary", "once"] = "toggle"
    on: bool = False
    used: bool = False


@component
@dataclass(slots=True)
class PressurePlate:
    """Its `Switch` is on while its `Trigger` has the player inside."""


@component
@dataclass(slots=True)
class Pickup:
    value: int = 1


@dataclass(frozen=True, slots=True)
class TriggerEntered:
    iid: str


@dataclass(frozen=True, slots=True)
class TriggerExited:
    iid: str


@dataclass(frozen=True, slots=True)
class Interacted:
    iid: str


@dataclass(frozen=True, slots=True)
class SwitchChanged:
    iid: str
    on: bool


@dataclass(frozen=True, slots=True)
class Collected:
    iid: str
    value: int


def overlap(a: Body, b: Body, margin: float = 0.0) -> bool:
    """Whether the boxes overlap once `a` grows by `margin` on every side."""
    return (
        a.x - margin < b.x + b.width
        and b.x < a.x + a.width + margin
        and a.y - margin < b.y + b.height
        and b.y < a.y + a.height + margin
    )


def player_body(world: World) -> Body | None:
    """The living player's body, if any."""
    for _, body, motor in world.query(Body, Motor):
        if not motor.dead:
            return body
    return None


def set_switch(world: World, eid: EntityId, switch: Switch, on: bool) -> None:
    if switch.on != on:
        switch.on = on
        world.resource(EventBus).publish(SwitchChanged(world.get(eid, Identity).iid, on))


def interact_system(world: World, dt: float) -> None:
    """Mark the nearest interactable in reach; using it flips its switch."""
    actions = world.resource(InputState)
    player = player_body(world)
    nearest: tuple[float, EntityId, Interactable] | None = None
    for eid, body, interactable in world.query(Body, Interactable):
        interactable.in_range = False
        if player is not None and overlap(body, player, interactable.reach):
            dx = body.center_x - player.center_x
            dy = (body.y + body.height / 2) - (player.y + player.height / 2)
            if nearest is None or dx * dx + dy * dy < nearest[0]:
                nearest = (dx * dx + dy * dy, eid, interactable)
    chosen = None
    if nearest is not None:
        _, chosen, interactable = nearest
        interactable.in_range = True
        if actions.pressed(Action.INTERACT):
            world.resource(EventBus).publish(Interacted(world.get(chosen, Identity).iid))
            switch = world.find(chosen, Switch)
            if switch is not None and switch.mode == "toggle":
                set_switch(world, chosen, switch, not switch.on)
            elif switch is not None and switch.mode == "once" and not switch.used:
                switch.used = True
                set_switch(world, chosen, switch, True)
    for eid, switch, _ in world.query(Switch, Interactable):
        if switch.mode == "momentary":
            set_switch(world, eid, switch, eid == chosen and actions.down(Action.INTERACT))


def trigger_system(world: World, dt: float) -> None:
    player = player_body(world)
    bus = world.resource(EventBus)
    for eid, body, trigger in world.query(Body, Trigger):
        inside = player is not None and overlap(body, player)
        if inside != trigger.inside:
            trigger.inside = inside
            iid = world.get(eid, Identity).iid
            bus.publish(TriggerEntered(iid) if inside else TriggerExited(iid))


def plate_system(world: World, dt: float) -> None:
    for eid, trigger, switch, _ in world.query(Trigger, Switch, PressurePlate):
        set_switch(world, eid, switch, trigger.inside)


def pickup_system(world: World, dt: float) -> None:
    player = player_body(world)
    if player is None:
        return
    bus, spawner = world.resource(EventBus), world.resource(Spawner)
    for eid, body, pickup in list(world.query(Body, Pickup)):
        if overlap(body, player):
            bus.publish(Collected(world.get(eid, Identity).iid, pickup.value))
            spawner.retire(eid)
