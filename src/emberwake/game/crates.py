"""Pushable crates: boxes the player shoves, drops and stacks, and that weigh pressure plates.

Rules: docs/specs/push-crates.md. A crate is stepped with the engine's box mover, so it behaves
the same on every platform. `crate_system` runs right after the player, whose own collision
reads `crate_solids`. Where a crate has been moved to is saved by iid (`CrateRest`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.ecs import component
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, TileSource, move
from emberwake.engine.world.spawning import WorldState
from emberwake.game.actions import Action
from emberwake.game.platforms import platform_solids
from emberwake.game.player.controller import Motor

if TYPE_CHECKING:
    from emberwake.engine.ecs import World
    from emberwake.engine.world.spawning import WorldState

FLUSH = 0.5
"""How close, in px, counts as touching."""


@dataclass(frozen=True, slots=True)
class CrateTuning:
    """Push crates (content/feel.toml, ``[crates]``). px/s and px/s²."""

    push_speed: float = 60.0
    """Speed of a pushed crate, and of the player pushing it."""
    gravity: float = 1200.0
    max_fall: float = 360.0


@component
@dataclass(slots=True)
class PushCrate:
    """A box that falls, stacks and is pushed by the player walking into it."""

    vy: float = 0.0
    placed: bool = False
    """Its saved offset has been applied since it spawned."""
    home_x: float = 0.0
    home_y: float = 0.0
    """Where the level puts it."""


@component
@dataclass(slots=True)
class CrateRest:
    """Where a crate was left, as an offset from its home. Saved by iid."""

    dx: float = 0.0
    dy: float = 0.0


def crate_solids(world: World) -> list[Body]:
    """The boxes the player's collision treats as solid."""
    return [body for _, body, _ in world.query(Body, PushCrate)]


def place_crates(world: World, dt: float = 0.0) -> None:
    """Move freshly spawned crates to where they were left."""
    for _, body, crate, rest in world.query(Body, PushCrate, CrateRest):
        if not crate.placed:
            crate.placed = True
            crate.home_x, crate.home_y = body.x, body.y
            body.x, body.y = body.x + rest.dx, body.y + rest.dy


def reset_crates(world: World, state: WorldState) -> None:
    """Send every crate home: live ones at once, unloaded ones by forgetting where they rest."""
    for iid, saved in list(state.entities.items()):
        if saved.pop("CrateRest", None) is not None and not saved:
            del state.entities[iid]
    for _, body, crate, rest in world.query(Body, PushCrate, CrateRest):
        _home(body, crate, rest)


def _home(body: Body, crate: PushCrate, rest: CrateRest) -> None:
    body.x, body.y = crate.home_x, crate.home_y
    crate.vy = 0.0
    rest.dx = rest.dy = 0.0


def crate_system(world: World, dt: float) -> None:
    """Push crates the player walks into, then let every crate fall and settle, bottom first."""
    place_crates(world)
    crates = sorted(
        world.query(Body, PushCrate, CrateRest), key=lambda found: (-found[1].bottom, found[0])
    )
    if not crates:
        return
    tuning, grid = world.resource(CrateTuning), world.resource(TileSource)
    player = _player(world)
    solids = [*(body for _, body, _, _ in crates), *platform_solids(world)]
    if player is not None:
        solids.append(player[0])
    for _, body, crate, rest in crates:
        side = player[2] if player is not None and _against(player[0], body, player[2]) else 0
        crate.vy = min(crate.vy + tuning.gravity * dt, tuning.max_fall)
        contacts = move(grid, body, side * tuning.push_speed * dt, crate.vy * dt, solids=solids)
        if contacts.ground or contacts.ceiling:
            crate.vy = 0.0
        if side and player is not None and not (contacts.left or contacts.right):
            player[1].vx = side * tuning.push_speed
        if grid.void(body.center_x, body.y):
            _home(body, crate, rest)
        rest.dx, rest.dy = body.x - crate.home_x, body.y - crate.home_y


def _player(world: World) -> tuple[Body, Motor, int] | None:
    """The living player's body and motor, and the way they are pushing (0 when not)."""
    for _, body, motor in world.query(Body, Motor):
        if not motor.dead:
            side = world.resource(InputState).axis(Action.LEFT, Action.RIGHT)
            pushing = motor.grounded and motor.dash_ticks == 0
            return body, motor, side if pushing else 0
    return None


def _against(player: Body, crate: Body, side: int) -> bool:
    """Whether the player is flush with the crate's side and pushing toward it."""
    gap = crate.x - (player.x + player.width) if side > 0 else player.x - (crate.x + crate.width)
    level = player.y < crate.bottom - FLUSH and crate.y < player.bottom - FLUSH
    return side != 0 and level and abs(gap) < FLUSH
