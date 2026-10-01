"""ECS-lite: entities as component stores, typed queries, resources and a phase schedule.

Pure Python, no pygame. Components are slotted dataclasses, so serde saves them.
"""

from emberwake.engine.ecs.registry import COMPONENTS, Registry, component
from emberwake.engine.ecs.schedule import Schedule, System
from emberwake.engine.ecs.world import EntityId, World

__all__ = ["COMPONENTS", "EntityId", "Registry", "Schedule", "System", "World", "component"]
