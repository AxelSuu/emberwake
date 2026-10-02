"""Story beats: the slice's cutscene scripts and the stage they draw on.

A script drives a `Director` (the gameplay scene's side of a cutscene) and its `Stage`. Every
script runs to the same end state when skipped, so skipping never loses a flag or a lamp.
See ``docs/specs/story-beats.md``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from emberwake.engine.core.cutscene import wait
from emberwake.engine.ecs import component
from emberwake.game.flags import Facts
from emberwake.game.interact import Interactable
from emberwake.game.light import LightSource

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.core.cutscene import Script
    from emberwake.engine.ecs import World

FADE_IN = 1.5
FADE_STEPS = 30
LAMP_STEP = 0.15
GREAT_LIGHT = LightSource(radius=140.0, strength=1.0, color="#fbb954")
STORY_FLAGS = ("great_lamp", "hesper_stage", "quill_stage")
"""Flags the scripts set besides ``story_<name>``."""


@dataclass(slots=True)
class Stage:
    """What a cutscene shows besides the world."""

    fade: float = 0.0
    """0 clear, 1 black."""
    focus: tuple[float, float] | None = None
    """World px the camera aims at instead of the player."""
    caption: str = ""
    """A string key, shown in the lower third."""

    def clear(self) -> None:
        self.fade, self.focus, self.caption = 0.0, None, ""


@component
@dataclass(slots=True)
class StoryBeat:
    """A zone that plays its script the first time the player enters it."""

    script: str = ""


@component
@dataclass(slots=True)
class GreatLamp:
    """The Great Lamp: kindled once the Lamprey is dead, which plays ``great_lamp``."""

    lit: bool = False


def great_lamp_system(world: World, dt: float) -> None:
    """The Great Lamp can be kindled after the Lamprey, and burns once `great_lamp` is set."""
    from emberwake.game.lamprey import DEFEATED  # noqa: PLC0415  (lamprey imports components)

    facts = world.resource(Facts)
    lit = bool(facts.get("great_lamp"))
    ready = bool(facts.get(DEFEATED)) and not lit
    for eid, lamp in world.query(GreatLamp):
        lamp.lit = lit
        if ready != world.has(eid, Interactable):
            if ready:
                world.add(eid, Interactable(prompt="kindle"))
            else:
                world.remove(eid, Interactable)
        if lit != world.has(eid, LightSource):
            if lit:
                world.add(eid, dataclasses.replace(GREAT_LIGHT))
            else:
                world.remove(eid, LightSource)


class Director(Protocol):
    stage: Stage

    def locate(self, prefab: str) -> tuple[float, float] | None:
        """Centre of the first loaded entity of `prefab`, if any."""
        ...

    def set_flag(self, name: str, value: int) -> None: ...

    def area_lamps(self) -> list[str]:
        """Iids of every Lamp in the player's area, nearest the camera's focus first."""
        ...

    def light_lamp(self, iid: str) -> None:
        """Light a lamp for good, loaded or not."""
        ...

    def flash(self) -> None: ...

    def recount(self) -> None:
        """Recount the areas' light after lamps lit outside the loaded rooms."""
        ...

    def credits(self) -> None: ...


def flag(name: str) -> str:
    return f"story_{name}"


def caption(stage: Stage, key: str, seconds: float) -> Script:
    stage.caption = key
    yield wait(seconds)
    stage.caption = ""


def intro(director: Director) -> Script:
    stage = director.stage
    stage.fade, stage.focus = 1.0, director.locate("beacon")
    for step in range(1, FADE_STEPS + 1):
        yield wait(FADE_IN / FADE_STEPS)
        stage.fade = 1 - step / FADE_STEPS
    yield from caption(stage, "story.intro.1", 2.5)
    yield from caption(stage, "story.intro.2", 2.5)
    stage.focus = None
    yield wait(1.0)
    director.set_flag(flag("intro"), 1)
    stage.clear()


def lamprey_reveal(director: Director) -> Script:
    stage = director.stage
    stage.focus = director.locate("lamprey")
    yield wait(1.0)
    yield from caption(stage, "story.lamprey.1", 2.0)
    yield from caption(stage, "story.lamprey.2", 2.0)
    stage.focus = None
    yield wait(0.8)
    director.set_flag(flag("lamprey_reveal"), 1)
    stage.clear()


def great_lamp(director: Director) -> Script:
    stage = director.stage
    stage.focus = director.locate("great_lamp")
    yield wait(0.8)
    director.flash()
    for iid in director.area_lamps():
        director.light_lamp(iid)
        yield wait(LAMP_STEP)
    director.recount()
    director.set_flag("great_lamp", 1)
    director.set_flag("hesper_stage", 1)
    director.set_flag("quill_stage", 2)
    yield from caption(stage, "story.great_lamp.1", 2.5)
    yield from caption(stage, "story.great_lamp.2", 2.5)
    director.set_flag(flag("great_lamp"), 1)
    stage.clear()
    director.credits()


SCRIPTS: dict[str, Callable[[Director], Script]] = {
    "intro": intro,
    "lamprey_reveal": lamprey_reveal,
    "great_lamp": great_lamp,
}
