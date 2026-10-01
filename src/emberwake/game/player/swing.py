"""The lantern swing: the player's melee, pogo and the way it touches the world.

Rules: docs/specs/lantern-swing.md. `swing_system` (logic phase) starts swings and moves their
hitbox through windup, active and recovery; `combat_system` hurts enemies; `strike_system`
(post phase, after combat) turns what the active hitbox touched into pogo, recoil and `Struck`
events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, component
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, Tile, TileSource, overlaps
from emberwake.game.actions import Action
from emberwake.game.combat import Hitbox, Team
from emberwake.game.interact import overlap
from emberwake.game.player.controller import Motor
from emberwake.game.player.tuning import PlayerTuning

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

HAZARDS = frozenset({Tile.HAZARD})
SOLIDS = frozenset({Tile.SOLID})


class Direction(StrEnum):
    FORWARD = "forward"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class SwingTuning:
    """Frame data and forces of the swing (content/feel.toml, ``[swing]``): ticks, px, px/s."""

    windup: int = 2
    active: int = 5
    recovery: int = 7
    buffer: int = 6
    damage: int = 1
    knockback: float = 160.0
    reach: float = 22.0
    """Width of the forward hitbox and height of the up and down ones."""
    pogo_speed: float = 260.0
    recoil: float = 90.0
    hitstop: int = 2
    """Ticks the scene freezes on an enemy hit."""
    trauma: float = 0.12
    stagger: float = 0.25
    """Seconds an enemy is knocked about after a hit."""

    @property
    def length(self) -> int:
        return self.windup + self.active + self.recovery


@component
@dataclass(slots=True)
class Swing:
    """The player's swing state. `tick` 0 is idle; otherwise ticks since the swing started."""

    tick: int = 0
    direction: Direction = Direction.FORWARD
    facing: int = 1
    hits: int = 0
    """Enemies the current swing has hit so far."""
    struck: list[EntityId] = field(default_factory=list)
    """Strikeable entities the current swing has already struck."""
    bounced: bool = False
    recoiled: bool = False

    def progress(self, tuning: SwingTuning) -> float:
        """0 to 1 through the swing, for drawing; 0 when idle."""
        return min(self.tick / tuning.length, 1.0) if self.tick else 0.0


@component
@dataclass(slots=True)
class Strikeable:
    """Reacts to the swing: gets a `Struck` event, at most once per swing."""

    bouncy: bool = False
    """A down swing bounces off it like off an enemy."""
    solid: bool = False
    """A forward swing recoils off it like off a wall."""
    struck: Direction | None = None
    """How a swing struck it this tick, if one did, for systems that react after the strike."""


@dataclass(frozen=True, slots=True)
class Struck:
    target: EntityId
    direction: Direction
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class SwingStarted:
    direction: Direction
    facing: int


@dataclass(frozen=True, slots=True)
class SwingHit:
    """The swing hit an enemy, bounced or clanged off a wall: where, for sparks and sound."""

    x: float
    y: float
    enemy: bool


def hitbox_geometry(
    direction: Direction, body: Body, reach: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Offset and size of the swing's hitbox from the body's top left, facing right."""
    span = body.width + 14
    side = (body.width - span) / 2
    match direction:
        case Direction.UP:
            return (side, -reach + 4), (span, reach)
        case Direction.DOWN:
            return (side, body.height - 4), (span, reach)
        case _:
            return (body.width - 4, 1), (reach, body.height - 2)


def swing_system(world: World, dt: float) -> None:
    """Start swings on input and advance them, keeping the hitbox in step with the phases."""
    actions, tuning = world.resource(InputState), world.resource(SwingTuning)
    for _, body, motor, swing, hitbox in world.query(Body, Motor, Swing, Hitbox):
        if motor.dead or motor.dash_ticks > 0:
            _stop(swing, hitbox)
            continue
        if swing.tick:
            swing.tick += 1
            if swing.tick == tuning.windup + 1:
                hitbox.activate()
            elif swing.tick == tuning.windup + tuning.active + 1:
                hitbox.deactivate()
            if swing.tick > tuning.length:
                _stop(swing, hitbox)
        if not swing.tick and actions.pressed_within(Action.SWING, tuning.buffer):
            actions.consume(Action.SWING)
            _start(world, body, motor, swing, hitbox, tuning)


def _start(  # noqa: PLR0917
    world: World, body: Body, motor: Motor, swing: Swing, hitbox: Hitbox, tuning: SwingTuning
) -> None:
    actions = world.resource(InputState)
    if actions.down(Action.UP):
        direction = Direction.UP
    elif actions.down(Action.DOWN) and not motor.grounded:
        direction = Direction.DOWN
    else:
        direction = Direction.FORWARD
    swing.tick, swing.direction, swing.facing = 1, direction, motor.facing
    swing.hits, swing.bounced, swing.recoiled = 0, False, False
    swing.struck.clear()
    hitbox.offset, hitbox.size = hitbox_geometry(direction, body, tuning.reach)
    hitbox.flip = motor.facing < 0
    hitbox.damage, hitbox.knockback, hitbox.targets = tuning.damage, tuning.knockback, Team.ENEMY
    hitbox.deactivate()
    if tuning.windup == 0:
        hitbox.activate()
    world.resource(EventBus).publish(SwingStarted(direction, motor.facing))


def _stop(swing: Swing, hitbox: Hitbox) -> None:
    swing.tick = 0
    hitbox.deactivate()


def strike_system(world: World, dt: float) -> None:
    """Pogo, recoil and `Struck` events for whatever an active swing touches."""
    bus, grid = world.resource(EventBus), world.resource(TileSource)
    tuning, player = world.resource(SwingTuning), world.resource(PlayerTuning)
    for _, strikeable in world.query(Strikeable):
        strikeable.struck = None
    for _, body, motor, swing, hitbox in world.query(Body, Motor, Swing, Hitbox):
        if not hitbox.active:
            continue
        area = hitbox.area(body)
        cx, cy = area.center_x, area.y + area.height / 2
        if len(hitbox.hit) > swing.hits:
            swing.hits = len(hitbox.hit)
            bus.publish(SwingHit(cx, cy, enemy=True))
            _react(swing, motor, tuning, player, bounce=True, solid=True)
        for target, target_body, strikeable in world.query(Body, Strikeable):
            if target in swing.struck or not overlap(area, target_body):
                continue
            swing.struck.append(target)
            strikeable.struck = swing.direction
            centre_y = target_body.y + target_body.height / 2
            bus.publish(Struck(target, swing.direction, target_body.center_x, centre_y))
            _react(swing, motor, tuning, player, bounce=strikeable.bouncy, solid=strikeable.solid)
        rect = (area.x, area.y, area.width, area.height)
        down = swing.direction is Direction.DOWN
        if down and not swing.bounced and overlaps(grid, *rect, kinds=HAZARDS):
            bus.publish(SwingHit(cx, area.bottom, enemy=False))
            _react(swing, motor, tuning, player, bounce=True, solid=False)
        forward = swing.direction is Direction.FORWARD
        if forward and not swing.recoiled and overlaps(grid, *rect, kinds=SOLIDS):
            bus.publish(SwingHit(cx, cy, enemy=False))
            _react(swing, motor, tuning, player, bounce=False, solid=True)


def _react(
    swing: Swing,
    motor: Motor,
    tuning: SwingTuning,
    player: PlayerTuning,
    *,
    bounce: bool,
    solid: bool,
) -> None:
    if bounce and swing.direction is Direction.DOWN and not swing.bounced:
        swing.bounced = True
        motor.vy = -tuning.pogo_speed
        motor.var_jump = 0
        motor.grounded = motor.coyote_ok = False
        motor.dash_charges = max(motor.dash_charges, player.dash_charges)
    elif solid and swing.direction is Direction.FORWARD and not swing.recoiled:
        swing.recoiled = True
        motor.vx = -swing.facing * tuning.recoil
