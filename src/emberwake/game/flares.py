"""Throwable flares: physical props that glow, light the dark and burn out.

A flare is a `LightSource` riding on a physics prop, so it tumbles, bounces and settles on its
own, lights lightforms, refills the ember and scares shadow creatures while it lasts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.ecs import component
from emberwake.engine.input import InputState
from emberwake.engine.physics import Body, PropWorld
from emberwake.engine.world.rooms import RoomStreamer
from emberwake.game.actions import Action
from emberwake.game.interact import player_body
from emberwake.game.light import LightSource
from emberwake.game.player.controller import Motor

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

FLARE_SIZE = 6
FLARE_RADIUS = 80.0
FLARE_LIFE = 8.0
FADE = 1.5
"""Seconds over which a dying flare's light fades."""
COOLDOWN = 0.6
THROW = (150.0, -110.0)
"""Launch velocity for a right-facing throw, px/s."""
REFRESH = 0.25
"""Seconds between rebuilds of static geometry while flares are out (doors and lightforms move)."""
MARGIN = 2
"""Tiles around the active room that props collide with."""


@component
@dataclass(slots=True)
class Flare:
    life: float = FLARE_LIFE
    handle: int = -1


@dataclass(slots=True)
class FlareKit:
    """The prop world flares live in, and the throw cooldown."""

    props: PropWorld
    cooldown: float = 0.0
    since_refresh: float = 0.0


def throw_flare(world: World, kit: FlareKit, x: float, y: float, facing: int) -> int:
    """Spawn a flare at (`x`, `y`) thrown the way `facing` (-1 or 1) points; returns its entity."""
    handle = kit.props.add_circle(x, y, FLARE_SIZE / 2, mass=0.3, bounce=0.45)
    kit.props.push(handle, THROW[0] * facing, THROW[1])
    half = FLARE_SIZE / 2
    eid = world.spawn(
        Body(x - half, y - half, FLARE_SIZE, FLARE_SIZE),
        LightSource(radius=FLARE_RADIUS),
        Flare(handle=handle),
    )
    world.flush()
    return eid


def flare_system(world: World, dt: float) -> None:
    """Throw on request, move flares with their props and put out the spent ones."""
    kit = world.resource(FlareKit)
    kit.cooldown = max(kit.cooldown - dt, 0.0)
    player = player_body(world)
    actions = world.resource(InputState)
    if player is not None and kit.cooldown <= 0 and actions.pressed(Action.FLARE):
        facing = next((m.facing for _, m in world.query(Motor)), 1)
        throw_flare(world, kit, player.center_x + facing * 6, player.y + 8, facing)
        kit.cooldown = COOLDOWN
    flares = list(world.query(Body, Flare, LightSource))
    if not flares:
        kit.since_refresh = REFRESH
        return
    _keep_statics_current(world, kit, dt)
    if player is not None:
        motor = next(m for _, m in world.query(Motor))
        kit.props.set_player(player, motor.vx, motor.vy)
    kit.props.step(dt)
    for eid, body, flare, light in flares:
        state = kit.props.state(flare.handle)
        body.x, body.y = state.x - body.width / 2, state.y - body.height / 2
        flare.life -= dt
        light.strength = min(1.0, max(flare.life, 0.0) / FADE)
        if flare.life <= 0:
            kit.props.remove(flare.handle)
            world.despawn(eid)


def _keep_statics_current(world: World, kit: FlareKit, dt: float) -> None:
    kit.since_refresh += dt
    if kit.since_refresh < REFRESH:
        return
    kit.since_refresh = 0.0
    streamer = world.resource(RoomStreamer)
    if streamer.active is None:
        return
    rect = streamer.graph.rects[streamer.active]
    size = streamer.grid.tile_size
    column = math.floor(rect.left / size) - MARGIN
    row = math.floor(rect.top / size) - MARGIN
    columns = math.ceil(rect.width / size) + 2 * MARGIN
    rows = math.ceil(rect.height / size) + 2 * MARGIN
    kit.props.refresh((column, row, columns, rows))
