from __future__ import annotations

from emberwake.engine.core.dialogue import DialogueRunner, load_dialogues
from emberwake.game import paths
from emberwake.game.grants import load_grants

GRAPHS = load_dialogues(paths.content("dialogue.toml"))
GRANTS = load_grants(paths.content("grants.toml"))
ASK_LIGHTS = "dialogue.hesper.ask_lights"


def hesper(flags: dict[str, int]) -> DialogueRunner:
    return DialogueRunner(GRAPHS["hesper"], flags)


def ask_about_lights(run: DialogueRunner) -> list[str]:
    """Pick the lights question and read to the end of the answers; the actions on the way."""
    choice = [c.text for c in run.choices].index(ASK_LIGHTS)
    run.advance(choice)
    actions = run.take_actions()
    while not run.choices and not run.finished:
        run.advance()
        actions += run.take_actions()
    return actions


def test_hesper_pays_nothing_before_a_light_is_rescued() -> None:
    flags: dict[str, int] = {}
    run = hesper(flags)
    choice = [c.text for c in run.choices].index(ASK_LIGHTS)
    run.advance(choice)
    assert run.text == "dialogue.hesper.lights_wait"
    assert run.take_actions() == []
    assert not any(name.startswith("hesper_paid") for name in flags)


def test_each_threshold_pays_its_reward_once() -> None:
    flags = {"lost_lights": 1}
    assert ask_about_lights(hesper(flags)) == ["pay:50"]
    assert ask_about_lights(hesper(flags)) == []
    flags["lost_lights"] = 2
    assert ask_about_lights(hesper(flags)) == ["give:flare_pouch"]
    flags["lost_lights"] = 3
    assert ask_about_lights(hesper(flags)) == ["give:oil_flask"]
    assert ask_about_lights(hesper(flags)) == []
    assert (flags["hesper_paid_1"], flags["hesper_paid_2"], flags["hesper_paid_3"]) == (1, 1, 1)


def test_rewards_owed_together_are_all_paid_in_order() -> None:
    flags = {"lost_lights": 3}
    assert ask_about_lights(hesper(flags)) == ["pay:50", "give:flare_pouch", "give:oil_flask"]


def test_a_missed_threshold_is_not_skipped() -> None:
    flags = {"lost_lights": 2, "hesper_paid_1": 1}
    assert ask_about_lights(hesper(flags)) == ["give:flare_pouch"]


def test_hesper_greets_by_stage() -> None:
    assert hesper({}).text == "dialogue.hesper.hello"
    assert hesper({"met_hesper": 1}).text == "dialogue.hesper.welcome_back"
    assert hesper({"hesper_stage": 1}).text == "dialogue.hesper.lit"


def test_quill_greets_by_stage() -> None:
    def greeting(flags: dict[str, int]) -> str:
        return DialogueRunner(GRAPHS["quill"], flags).text

    assert greeting({}) == "dialogue.quill.hello"
    assert greeting({"met_quill": 1}) == "dialogue.quill.welcome_back"
    assert greeting({"quill_stage": 1}) == "dialogue.quill.square"
    assert greeting({"quill_stage": 2, "met_quill": 1}) == "dialogue.quill.road"


def test_quill_opens_her_shop() -> None:
    run = DialogueRunner(GRAPHS["quill"], {})
    run.advance([c.text for c in run.choices].index("dialogue.quill.ask_map"))
    assert run.take_actions() == ["shop:quill"]


def test_every_give_names_a_grant() -> None:
    for graph in GRAPHS.values():
        for node in graph.values():
            if node.action.startswith("give:"):
                assert node.action.removeprefix("give:") in GRANTS
