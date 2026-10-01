"""Combat basics: health, hit and hurt boxes on teams, knockback, invulnerability frames.

A `Hitbox` deals damage to entities with a `Health`, a `Hurtbox` and a `Body` whose team it
targets. Each activation of a hitbox hurts a target at most once, and a hurt target ignores
hits for `Health.iframes` seconds. What happens next is for other systems to decide: they listen
for `Damaged` and `Killed` on the event bus (feedback, sound, score) and movers consume
`Knockback`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, component
from emberwake.engine.physics import Body
from emberwake.game.interact import overlap

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

KNOCKBACK_LIFT = 0.4
"""Fraction of a knockback's strength that also pushes up."""


class Team(IntFlag):
    """Collision layers for combat; a hitbox's `targets` is a mask of these."""

    NONE = 0
    PLAYER = 1
    ENEMY = 2
    HAZARD = 4
    ALL = PLAYER | ENEMY | HAZARD


@component
@dataclass(slots=True)
class Health:
    max: int = 3
    current: int = -1
    """Hit points left; a negative start means full."""
    iframes: float = 0.6
    """Seconds of invulnerability after being hurt."""
    invulnerable: float = 0.0
    """Seconds of invulnerability left."""
    dead: bool = False

    def __post_init__(self) -> None:
        if self.current < 0:
            self.current = self.max


@component
@dataclass(slots=True)
class Hurtbox:
    """Lets an entity's body be hurt. `team` is the layer hitboxes aim at."""

    team: Team = Team.ENEMY


@component
@dataclass(slots=True)
class Hitbox:
    """A damaging area attached to an entity, placed relative to its body's top left."""

    damage: int = 1
    targets: Team = Team.ENEMY
    offset: tuple[float, float] = (0.0, 0.0)
    size: tuple[float, float] = (16.0, 16.0)
    knockback: float = 120.0
    flip: bool = False
    """Mirror the offset across the body's centre, for an attacker facing left."""
    active: bool = False
    hit: list[int] = field(default_factory=list)
    """Entities already hurt by this activation."""

    def activate(self) -> None:
        """Start a new swing."""
        self.active = True
        self.hit.clear()

    def deactivate(self) -> None:
        self.active = False

    def area(self, body: Body) -> Body:
        """The hitbox's rectangle in world space for an owner at `body`."""
        x, y = self.offset
        w, h = self.size
        left = body.x + (body.width - x - w if self.flip else x)
        return Body(left, body.y + y, w, h)


@component
@dataclass(slots=True)
class Knockback:
    """An impulse for the mover to apply and then clear."""

    vx: float = 0.0
    vy: float = 0.0


@dataclass(frozen=True, slots=True)
class Damaged:
    target: EntityId
    attacker: EntityId
    amount: int
    health: int
    """Hit points left after this hit."""
    x: float
    y: float
    """Where the target was hit (its centre)."""
    knockback_x: float
    knockback_y: float


@dataclass(frozen=True, slots=True)
class Killed:
    target: EntityId
    attacker: EntityId


def combat_system(world: World, dt: float) -> None:
    """Tick invulnerability, then resolve every active hitbox against every hurtbox."""
    for _, health in world.query(Health):
        health.invulnerable = max(health.invulnerable - dt, 0.0)
    bus = world.resource(EventBus)
    hurtable = list(world.query(Body, Health, Hurtbox))
    for attacker, owner, hitbox in list(world.query(Body, Hitbox)):
        if not hitbox.active:
            continue
        area = hitbox.area(owner)
        for target, body, health, hurtbox in hurtable:
            if target == attacker or target in hitbox.hit:
                continue
            if health.dead or health.invulnerable > 0 or not hitbox.targets & hurtbox.team:
                continue
            if not overlap(area, body):
                continue
            hitbox.hit.append(target)
            health.current = max(health.current - hitbox.damage, 0)
            health.invulnerable = health.iframes
            side = 1.0 if body.center_x >= owner.center_x else -1.0
            push, lift = hitbox.knockback * side, -hitbox.knockback * KNOCKBACK_LIFT
            _knock(world, target, push, lift)
            centre = body.y + body.height / 2
            damage = hitbox.damage
            bus.publish(
                Damaged(target, attacker, damage, health.current, body.center_x, centre, push, lift)
            )
            if health.current == 0:
                health.dead = True
                bus.publish(Killed(target, attacker))


def _knock(world: World, target: EntityId, vx: float, vy: float) -> None:
    if world.has(target, Knockback):
        impulse = world.get(target, Knockback)
        impulse.vx, impulse.vy = vx, vy
    else:
        world.add(target, Knockback(vx, vy))
