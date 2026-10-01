"""Room transitions: which room the player is in, streaming around it, and the upward boost."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.physics import Body
from emberwake.engine.world.rooms import RoomEntered, RoomStreamer
from emberwake.game.player.controller import Motor

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


@dataclass(frozen=True, slots=True)
class RoomTuning:
    entry_boost: float = 240
    """Upward speed (px/s) given when entering a room through its floor, so it is not lost."""


def room_system(world: World, dt: float) -> None:
    """Make the room holding the player's centre active and publish `RoomEntered`."""
    streamer = world.resource(RoomStreamer)
    graph = streamer.graph
    for _, body, motor in world.query(Body, Motor):
        room = graph.room_at(body.center_x, body.y + body.height / 2)
        if room is None or room == streamer.active:
            continue
        previous = streamer.active
        streamer.enter(room)
        if previous is not None and graph.rects[previous].top == graph.rects[room].bottom:
            motor.vy = min(motor.vy, -world.resource(RoomTuning).entry_boost)
        world.resource(EventBus).publish(RoomEntered(room, previous, body.center_x, body.bottom))
