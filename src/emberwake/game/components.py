"""Game components that prefabs (content/prefabs.toml) refer to by name."""

from __future__ import annotations

from dataclasses import dataclass

from emberwake.engine.ecs import component


@component
@dataclass(slots=True)
class Sprite:
    image: str
    """Placeholder art name, drawn to fill the entity's body (see game/render/placeholder.py)."""
