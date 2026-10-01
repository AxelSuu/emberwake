"""Sprite state from gameplay state, decided once per tick before drawing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.game.components import Sprite
from emberwake.game.interact import Switch
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


def sprite_system(world: World, dt: float) -> None:
    for eid, sprite in world.query(Sprite):
        switch, door = world.find(eid, Switch), world.find(eid, Door)
        sprite.active = (switch is not None and switch.on) or (door is not None and door.open)
