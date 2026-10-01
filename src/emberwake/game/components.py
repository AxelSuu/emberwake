"""Game components that prefabs (content/prefabs.toml) refer to by name.

Importing this module registers every game component, so tools that read prefabs import it.
"""

from __future__ import annotations

from dataclasses import dataclass

from emberwake.engine.ecs import component


@component
@dataclass(slots=True)
class Sprite:
    image: str
    """Placeholder art name, drawn to fill the entity's body (see game/render/placeholder.py)."""
    active_image: str | None = None
    """Drawn instead while the entity is active: a switch on, a door open."""
    active: bool = False

    @property
    def current(self) -> str:
        return self.active_image if self.active and self.active_image else self.image


# Modules defining components, imported for their registration.
from emberwake.game import (  # noqa: E402, F401
    beacons,
    combat,
    dialogue,
    enemies,
    flares,
    interact,
    light,
    signals,
)
from emberwake.game.player import controller  # noqa: E402, F401
