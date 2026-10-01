"""NPCs: entities that start a conversation when the player interacts with them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import component
from emberwake.game.interact import Interactable

if TYPE_CHECKING:
    from emberwake.engine.ecs import World


@component
@dataclass(slots=True)
class Npc:
    dialogue: str = ""
    """Name of a graph in ``content/dialogue.toml``."""


@dataclass(frozen=True, slots=True)
class Talk:
    """The player started talking to someone."""

    dialogue: str


def npc_system(world: World, dt: float) -> None:
    """Start a conversation with each NPC the player just used."""
    for _, interactable, npc in world.query(Interactable, Npc):
        if interactable.used:
            world.resource(EventBus).publish(Talk(npc.dialogue))
