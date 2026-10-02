from __future__ import annotations

from dataclasses import dataclass, field

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.cutscene import CutscenePlayer
from emberwake.engine.ecs import EntityId, World
from emberwake.game.components import Sprite
from emberwake.game.flags import Facts
from emberwake.game.interact import Interactable
from emberwake.game.light import LightSource
from emberwake.game.story import (
    SCRIPTS,
    GreatLamp,
    Stage,
    great_lamp_system,
)

STEP = 1 / 60


@dataclass
class FakeDirector:
    stage: Stage = field(default_factory=Stage)
    flags: dict[str, int] = field(default_factory=dict)
    lamps: list[str] = field(default_factory=lambda: ["near", "far"])
    lit: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def locate(self, prefab: str) -> tuple[float, float] | None:
        return (100.0, 50.0) if prefab != "missing" else None

    def set_flag(self, name: str, value: int) -> None:
        self.flags[name] = value

    def area_lamps(self) -> list[str]:
        return list(self.lamps)

    def light_lamp(self, iid: str) -> None:
        self.lit.append(iid)

    def flash(self) -> None:
        self.log.append("flash")

    def recount(self) -> None:
        self.log.append("recount")

    def credits(self) -> None:
        self.log.append("credits")


def run(name: str, *, skip: bool = False, seconds: float = 30.0) -> FakeDirector:
    director = FakeDirector()
    player = CutscenePlayer()
    player.play(SCRIPTS[name](director))
    if skip:
        player.skip()
    for _ in range(round(seconds / STEP)):
        player.update(STEP)
    assert not player.active
    return director


def test_the_intro_starts_black_on_the_beacon_and_fades_in():
    director, player = FakeDirector(), CutscenePlayer()
    player.play(SCRIPTS["intro"](director))
    assert director.stage.fade == 1.0
    assert director.stage.focus == (100.0, 50.0)
    for _ in range(round(1.5 / STEP)):
        player.update(STEP)
    assert director.stage.fade == 0.0
    assert director.stage.caption == "story.intro.1"


def test_every_script_played_or_skipped_ends_with_its_flag_and_a_clear_stage():
    for name in SCRIPTS:
        for skip in (False, True):
            director = run(name, skip=skip)
            assert director.flags[f"story_{name}"] == 1, (name, skip)
            assert director.stage == Stage(), (name, skip)


def test_the_great_lamp_lights_every_lamp_sets_the_stages_and_rolls_the_credits():
    for skip in (False, True):
        director = run("great_lamp", skip=skip)
        assert director.lit == ["near", "far"]
        assert {k: director.flags[k] for k in ("great_lamp", "hesper_stage", "quill_stage")} == {
            "great_lamp": 1,
            "hesper_stage": 1,
            "quill_stage": 2,
        }
        assert director.log == ["flash", "recount", "credits"]


def lamp_world(flags: dict[str, int]) -> tuple[World, EntityId]:
    world = World()
    world.insert_resource(Facts(flags, [], {}))
    eid = world.spawn(GreatLamp(), Sprite("great_lamp", "great_lamp_lit"))
    world.flush()
    great_lamp_system(world, STEP)
    world.flush()
    return world, eid


def test_the_great_lamp_waits_for_the_lamprey_then_burns_once_kindled():
    world, eid = lamp_world({})
    assert not world.has(eid, Interactable)
    assert not world.has(eid, LightSource)
    world, eid = lamp_world({"lamprey_defeated": 1})
    assert world.get(eid, Interactable).prompt == "kindle"
    world, eid = lamp_world({"lamprey_defeated": 1, "great_lamp": 1})
    assert not world.has(eid, Interactable)
    assert world.has(eid, LightSource)
    assert world.get(eid, GreatLamp).lit
