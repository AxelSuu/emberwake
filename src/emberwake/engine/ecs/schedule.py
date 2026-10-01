"""Systems grouped into named phases that run in a fixed order."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from emberwake.engine.ecs.world import World

type System = Callable[[World, float], None]


class Schedule:
    """Runs systems phase by phase, flushing the world's structural changes between phases.

    Within a phase, systems run in the order they were added, so a tick is deterministic.

    Example:
        >>> from emberwake.engine.ecs.world import World
        >>> log = []
        >>> schedule = Schedule(["logic", "physics"])
        >>> schedule.add("physics", lambda world, dt: log.append("move"))
        >>> schedule.add("logic", lambda world, dt: log.append("think"))
        >>> schedule.run(World(), 1 / 60)
        >>> log
        ['think', 'move']
    """

    def __init__(self, phases: Iterable[str]) -> None:
        self._phases: dict[str, list[System]] = {phase: [] for phase in phases}

    @property
    def phases(self) -> tuple[str, ...]:
        """Phase names in run order."""
        return tuple(self._phases)

    def add(self, phase: str, system: System) -> None:
        """Append `system` to `phase`.

        Raises:
            KeyError: `phase` is not one of this schedule's phases.
        """
        if phase not in self._phases:
            msg = f"unknown phase {phase!r}; phases are {self.phases}"
            raise KeyError(msg)
        self._phases[phase].append(system)

    def run(self, world: World, dt: float) -> None:
        """Flush `world`, then run every phase, flushing after each one."""
        world.flush()
        for systems in self._phases.values():
            for system in systems:
                system(world, dt)
            world.flush()
