"""Player movement: one deterministic step per tick. Rules: docs/specs/player-movement.md."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from emberwake.engine.core.mathx import approach, sign
from emberwake.engine.ecs import component
from emberwake.engine.physics import Body, Tile, move, overlaps
from emberwake.game.actions import Action

if TYPE_CHECKING:
    from emberwake.engine.input import InputState
    from emberwake.engine.physics import TileSource
    from emberwake.game.player.tuning import PlayerTuning

HAZARDS = frozenset({Tile.HAZARD})
NEVER = 1 << 30


class PlayerState(StrEnum):
    GROUND = "ground"
    AIR = "air"
    WALL_SLIDE = "wall_slide"
    DASH = "dash"


@dataclass(frozen=True, slots=True)
class Jumped:
    x: float
    y: float
    wall: int = 0
    """Side of the wall jumped off (-1 left, 1 right), or 0 for a normal jump."""


@dataclass(frozen=True, slots=True)
class Landed:
    x: float
    y: float
    speed: float


@dataclass(frozen=True, slots=True)
class Dashed:
    x: float
    y: float
    dx: float
    dy: float


@dataclass(frozen=True, slots=True)
class Died:
    x: float
    y: float


type PlayerEvent = Jumped | Landed | Dashed | Died


@component
@dataclass(slots=True)
class Motor:
    """Controller state of the player; its position and size are its `Body`."""

    vx: float = 0.0
    vy: float = 0.0
    facing: int = 1
    state: PlayerState = PlayerState.AIR
    grounded: bool = False
    on_one_way: bool = False
    air_ticks: int = NEVER
    coyote_ok: bool = False
    var_jump: int = 0
    wall_lock: int = 0
    wall_lock_dir: int = 0
    dash_charges: int = 1
    dash_ticks: int = 0
    dash_dir: tuple[float, float] = (0.0, 0.0)
    drop_ticks: int = 0
    dead: bool = False
    previous: tuple[float, float] = field(default=(0.0, 0.0))
    """Body position at the start of the last tick, for render interpolation."""


def new_player(foot_x: float, foot_y: float, tuning: PlayerTuning) -> tuple[Body, Motor]:
    """A player standing with the middle of its feet at (`foot_x`, `foot_y`)."""
    body = Body(foot_x - tuning.width / 2, foot_y - tuning.height, tuning.width, tuning.height)
    return body, Motor(dash_charges=tuning.dash_charges, previous=(body.x, body.y))


def step(  # noqa: PLR0917
    body: Body,
    motor: Motor,
    actions: InputState[Action],
    grid: TileSource,
    tuning: PlayerTuning,
    dt: float,
) -> list[PlayerEvent]:
    """Advance the player by one tick and return what happened."""
    return _Tick(body, motor, actions, grid, tuning, dt).run()


def wall_side(grid: TileSource, body: Body, reach: float) -> int:
    """-1 for a solid wall within `reach` px on the left, 1 on the right, else 0."""
    if overlaps(grid, body.x + body.width, body.y, reach, body.height):
        return 1
    if overlaps(grid, body.x - reach, body.y, reach, body.height):
        return -1
    return 0


class _Tick:
    """The working state of one `step` call."""

    def __init__(  # noqa: PLR0917
        self,
        body: Body,
        motor: Motor,
        actions: InputState[Action],
        grid: TileSource,
        tuning: PlayerTuning,
        dt: float,
    ) -> None:
        self.p = motor
        self.body = body
        self.actions = actions
        self.grid = grid
        self.t = tuning
        self.dt = dt
        self.events: list[PlayerEvent] = []
        self.intent_x = actions.axis(Action.LEFT, Action.RIGHT)
        self.intent_y = actions.axis(Action.UP, Action.DOWN)

    def run(self) -> list[PlayerEvent]:
        p, body = self.p, self.body
        p.previous = (body.x, body.y)
        if p.wall_lock > 0:
            p.wall_lock -= 1
            self.intent_x = p.wall_lock_dir
        if self.intent_x:
            p.facing = self.intent_x
        if not p.grounded:
            p.air_ticks = min(p.air_ticks + 1, NEVER)
        p.drop_ticks = max(p.drop_ticks - 1, 0)

        if p.dash_ticks == 0 and p.dash_charges > 0:
            self.try_dash()
        sliding = False
        if p.dash_ticks > 0:
            self.dash()
        else:
            sliding = self.run_and_fall()
            self.try_jump()
        if p.vy < 0:
            self.correct_corner()
        self.move()

        if p.dash_ticks > 0:
            p.state = PlayerState.DASH
        elif p.grounded:
            p.state = PlayerState.GROUND
        elif sliding:
            p.state = PlayerState.WALL_SLIDE
        else:
            p.state = PlayerState.AIR
        self.check_death()
        return self.events

    def try_dash(self) -> None:
        p, t = self.p, self.t
        if not self.actions.pressed_within(Action.DASH, t.jump_buffer):
            return
        self.actions.consume(Action.DASH)
        dx = self.intent_x or (0 if self.intent_y else p.facing)
        length = math.hypot(dx, self.intent_y)
        p.dash_dir = (dx / length, self.intent_y / length)
        p.dash_charges -= 1
        p.dash_ticks = t.dash_ticks
        p.var_jump = p.wall_lock = 0
        self.events.append(Dashed(self.body.center_x, self.body.bottom, *p.dash_dir))

    def dash(self) -> None:
        p, t = self.p, self.t
        dx, dy = p.dash_dir
        p.dash_ticks -= 1
        if p.dash_ticks > 0:
            p.vx, p.vy = dx * t.dash_speed, dy * t.dash_speed
        else:
            p.vx = dx * t.dash_end_speed
            p.vy = dy * t.dash_end_speed * (t.dash_end_up_mult if dy < 0 else 1)

    def run_and_fall(self) -> bool:
        """Horizontal acceleration, gravity and variable jump. Returns whether wall sliding."""
        p, t, dt = self.p, self.t, self.dt
        mult = 1.0 if p.grounded else t.air_mult
        target = self.intent_x * t.max_run
        if abs(p.vx) > t.max_run and sign(p.vx) == self.intent_x:
            p.vx = approach(p.vx, target, t.run_decel * mult * dt)
        else:
            p.vx = approach(p.vx, target, t.run_accel * mult * dt)

        sliding = (
            not p.grounded
            and p.vy >= 0
            and self.intent_x != 0
            and wall_side(self.grid, self.body, 1) == self.intent_x
        )
        max_fall = t.wall_slide_max if sliding else t.max_fall
        apex = abs(p.vy) < t.apex_threshold and self.actions.down(Action.JUMP)
        p.vy = approach(p.vy, max_fall, t.gravity * (t.apex_gravity_mult if apex else 1.0) * dt)

        if p.var_jump > 0:
            if self.actions.down(Action.JUMP):
                p.vy = min(p.vy, -t.jump_speed)
                p.var_jump -= 1
            else:
                p.var_jump = 0
                if p.vy < 0:
                    p.vy *= t.jump_cut
        return sliding

    def try_jump(self) -> None:
        p, t, body = self.p, self.t, self.body
        if not self.actions.pressed_within(Action.JUMP, t.jump_buffer):
            return
        if p.grounded and p.on_one_way and self.intent_y > 0:
            self.actions.consume(Action.JUMP)
            p.drop_ticks = t.drop_through
            p.grounded = p.coyote_ok = False
            return
        if p.grounded or (p.coyote_ok and p.air_ticks <= t.coyote):
            self.actions.consume(Action.JUMP)
            p.vy = -t.jump_speed
            p.vx += t.jump_h_boost * self.intent_x
            p.var_jump = t.var_jump
            p.grounded = p.coyote_ok = False
            self.events.append(Jumped(body.center_x, body.bottom))
            return
        wall = wall_side(self.grid, body, t.wall_jump_reach)
        if wall:
            self.actions.consume(Action.JUMP)
            p.vx = -wall * t.wall_jump_speed
            p.vy = -t.jump_speed
            p.var_jump = t.var_jump
            p.wall_lock = t.wall_jump_lock
            p.wall_lock_dir = p.facing = -wall
            self.events.append(Jumped(body.center_x, body.bottom, wall))

    def correct_corner(self) -> None:
        """Slide around ceiling corners clipped by at most `corner_correction` px."""
        p, grid, body = self.p, self.grid, self.body
        next_y = body.y + p.vy * self.dt
        if not overlaps(grid, body.x, next_y, body.width, body.height):
            return
        directions = (-1, 1) if p.vx == 0 else (sign(p.vx), -sign(p.vx))
        for offset in range(1, self.t.corner_correction + 1):
            for direction in directions:
                x = body.x + direction * offset
                free_now = not overlaps(grid, x, body.y, body.width, body.height)
                if free_now and not overlaps(grid, x, next_y, body.width, body.height):
                    body.x = x
                    return

    def move(self) -> None:
        p, body = self.p, self.body
        dropping = p.drop_ticks > 0
        impact = p.vy
        contacts = move(self.grid, body, p.vx * self.dt, p.vy * self.dt, drop_through=dropping)
        if contacts.left or contacts.right:
            p.vx = 0.0
        if contacts.ceiling and p.vy < 0:
            p.vy = 0.0
            p.var_jump = 0

        was_grounded = p.grounded
        if contacts.ground:
            p.grounded, p.on_one_way = True, contacts.one_way
            p.vy = 0.0
        elif p.vy >= 0:
            feet = Body(body.x, body.y, body.width, body.height)
            probe = move(self.grid, feet, 0, 1, drop_through=dropping)
            p.grounded, p.on_one_way = probe.ground, probe.one_way
        else:
            p.grounded = False

        if p.grounded:
            p.air_ticks = 0
            p.coyote_ok = True
            if p.dash_ticks == 0:
                p.dash_charges = self.t.dash_charges
            if not was_grounded:
                self.events.append(Landed(body.center_x, body.bottom, impact))

    def check_death(self) -> None:
        p, body, margin = self.p, self.body, self.t.hazard_margin
        inner = (
            body.x + margin,
            body.y + margin,
            body.width - 2 * margin,
            body.height - 2 * margin,
        )
        if overlaps(self.grid, *inner, kinds=HAZARDS) or self.grid.void(body.center_x, body.y):
            p.dead = True
            self.events.append(Died(body.center_x, body.bottom))
